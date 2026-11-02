#!/usr/bin/env python3
"""Export paper figure points, input thumbnails and paired native/metric poses.

No model inference, calibration, or scientific source files are modified.
The public site requires only static files, not a live Viser Python server.
"""
import argparse
import hashlib
import importlib.metadata
import json
import shutil
import sys
from pathlib import Path
import numpy as np
from PIL import Image
import viser
import viser.transforms as vtf
from patch_viser import patch_client

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ('physical-room', 'Physical · Room', 'physical-vggt-n15-e977460559eb', 'figure_physical-vggt-n15-e977460559eb_1791787329098124177.json', .052),
    ('physical-tabletop', 'Physical · Tabletop', 'physical-vggt-n15-8ffdf963c268', 'fig5_tabletop_ours_physical-vggt-n15-8ffdf963c268_1791794925115998810.json', .04),
    ('sim-room', 'Simulation · Room', 'three-vggt-n15-87205b6f6f1f', '1014_room_three-vggt-n15-87205b6f6f1f_1791943155635131751.json', .13),
    ('sim-tabletop', 'Simulation · Tabletop', 'three-vggt-n15-6cae8017d1b0', '1014_tabletop_589_three-vggt-n15-6cae8017d1b0_1791959072605370498.json', .13),
]
FILTERS = dict(confidence_percentile=10, dark_cutoff=0, max_distance=0, stride=1, sor_enabled=False)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def export(hevfm):
    if viser.__version__ != '1.0.24':
        raise RuntimeError('Export and client adapter require Viser 1.0.24')
    sys.path.insert(0, str(hevfm))
    from experiments.paper_assets.viewer import transformed, filter_mask, frustum_segments, origin_layers, PALETTE
    from experiments.paper_assets.common import load_case
    source_dir = hevfm / 'results/paper_assets_20260929'
    output = ROOT / 'docs/assets/scenes'
    output.mkdir(parents=True, exist_ok=True)
    client = ROOT / 'docs/vendor/viser'
    client.mkdir(parents=True, exist_ok=True)
    client_source = Path(viser.__file__).parent / 'client/build/index.html'
    (client/'index.html').write_text(patch_client(client_source.read_text()))
    dist = importlib.metadata.distribution('viser')
    license_file = next(item for item in dist.files if str(item).endswith('licenses/LICENSE'))
    shutil.copy2(dist.locate_file(license_file), client/'LICENSE')
    public = {'viser_version': viser.__version__, 'client': 'vendor/viser/index.html', 'scenes': []}
    provenance = {'viser_version': viser.__version__, 'upstream_client_sha256': digest(client_source), 'patched_client_sha256': digest(client/'index.html'), 'bridge_sha256': digest(client/'anchorhec-bridge.js'), 'patch': 'tools/patch_viser.py; docs/vendor/viser/anchorhec-bridge.js', 'cases': []}
    for slug, label, case_id, capture_name, frustum_size in CASES:
        full_case = load_case(source_dir, case_id)
        prepared_path = source_dir/'prepared'/f'{case_id}.json'
        prepared = json.loads(prepared_path.read_text())
        assert prepared['source_sha256'] == full_case['source_sha256']
        cloud_path = hevfm/prepared['cloud']
        assert digest(cloud_path) == prepared['cloud_sha256']
        capture_path = hevfm/'results/viser_figures'/capture_name
        capture = json.loads(capture_path.read_text())
        assert capture['case_id'] == case_id
        states = prepared['states']
        assert states['Ours']['fixed_pose_source'] == 'final v3 registration of the manuscript (registration_replay, 2026-10-05)'
        final = states['Ours']['fixed_final_source']
        assert digest(hevfm/final['summary']) == final['summary_sha256']
        np.testing.assert_array_equal(states['Raw']['anchor'], np.eye(4))
        assert states['Raw']['scale'] == 1
        physical = slug.startswith('physical')
        settings = dict(FILTERS)
        if physical:
            settings.update({key: capture['settings'][key] for key in FILTERS})
            assert capture['cloud_sha256'] == prepared['cloud_sha256']
        with np.load(cloud_path, allow_pickle=False) as cloud:
            raw, colors, confidence = cloud['raw_points'], cloud['colors'], cloud['confidence']
            mask = filter_mask(transformed(raw, states['Initial']), colors, confidence, settings)
            indices = np.flatnonzero(mask)
            ids = cloud['point_ids'][indices]
            if physical:
                selection_path = hevfm/capture['point_selection']
                assert digest(selection_path) == capture['point_selection_sha256']
                with np.load(selection_path, allow_pickle=False) as selection:
                    np.testing.assert_array_equal(ids, selection['point_ids'])
            points = raw[indices].astype(np.float32)
            rgb = colors[indices]
            source_count = len(raw)
        assert np.isfinite(points).all()
        state = states['Ours']; anchor = np.asarray(state['anchor']); scale = state['scale']
        transform = {'scale': scale, 'position': anchor[:3,3].tolist(), 'wxyz': vtf.SO3.from_matrix(anchor[:3,:3]).wxyz.tolist(), 'rotation': anchor[:3,:3].tolist()}
        fixed_ids = sorted({im['camera_index'] for im in prepared['images'] if im['role']=='fixed'})
        # Use one base-fixed view for both modes, including the raw geometry,
        # calibrated geometry, camera centers and robot-base axes. Quantiles
        # affect framing only: every selected point is still exported.
        view = capture['view']; orientation = vtf.SO3(np.asarray(view['wxyz'])).as_matrix()
        metric = transformed(points, state)
        low, high = np.quantile(metric @ orientation, [.03,.97], axis=0)
        raw_low, raw_high = np.quantile(points @ orientation, [.03,.97], axis=0)
        low, high = np.minimum(low, raw_low), np.maximum(high, raw_high)
        poses = np.asarray(state['wrist'] + state['fixed'] + states['Raw']['wrist'] + states['Raw']['fixed'])
        centers = np.vstack((poses[:,:3,3], np.zeros((1,3)), np.eye(3)*.3)) @ orientation
        low, high = np.minimum(low, centers.min(0)-frustum_size), np.maximum(high, centers.max(0)+frustum_size)
        center = (low+high)/2; radius = (high-low)/2
        fov = float(view['fov']); distance = (max(radius[:2])/np.tan(fov/2)+radius[2])*1.10
        target = center@orientation.T; position = target-orientation[:,2]*distance
        camera = {'position': position.tolist(), 'look_at': target.tolist(), 'up': (-orientation[:,1]).tolist(), 'fov': fov}
        record = {'id':slug,'label':label,'domain':'physical' if physical else 'simulation','case_id':case_id,'seed':prepared['case']['trial_seed'], 'points':len(points),'wrist_poses':15,'fixed_cameras':len(fixed_ids), 'point_size':.002,'point_shape':'square','filters':settings,'figure5_exact_points':physical,'transform':transform,'camera':camera,'inputs':[], 'poster':f'assets/images/scene-{slug}.png','note':'The last fixed-camera pose retains the fallback after registration rejection.' if slug=='sim-tabletop' else ''}
        audit = {'id':slug,'case_id':case_id,'prepared':str(prepared_path.relative_to(hevfm)),'prepared_sha256':digest(prepared_path),'cloud':prepared['cloud'],'cloud_sha256':digest(cloud_path),'source_sha256':prepared['source_sha256'],'capture':str(capture_path.relative_to(hevfm)),'capture_sha256':digest(capture_path),'filters':settings,'source_count':source_count,'display_count':len(points),'point_ids_sha256':hashlib.sha256(ids.tobytes()).hexdigest(),'figure5_saved_point_ids_equal':physical,'additional_downsampling':False,'filling':False,'framing':'Shared base-fixed view of Raw and Ours: saved viewing direction, union of both clouds’ 3–97% bounds, every camera center and base axes. No points removed by framing.','fixed_pose_source':state['fixed_pose_source'],'input_images':[]}
        server = viser.ViserServer(host='127.0.0.1', port=0, verbose=False)
        try:
            server.scene.set_up_direction('+z'); server.scene.world_axes.visible=False
            server.gui.configure_theme(dark_mode=False)
            server.scene.set_background_image(np.full((2,2,3),255,np.uint8),format='png')
            server.initial_camera.position=tuple(position);server.initial_camera.look_at=tuple(target)
            server.initial_camera.up=tuple(camera['up']);server.initial_camera.fov=fov
            server.scene.add_point_cloud('/pointmap',points=points,colors=rgb,point_size=.002/scale,point_shape='square',precision='float32',scale=scale,wxyz=tuple(transform['wxyz']),position=tuple(transform['position']))
            origin_layers(server.scene, state['frame'], grid=True, base=True)
            server.scene.add_frame('/Raw',show_axes=False,visible=False)
            server.scene.add_frame('/Ours',show_axes=False)
            thumbnails={}; raw_fixed=0
            images_dir=ROOT/'docs/assets/images/inputs'/slug;images_dir.mkdir(parents=True,exist_ok=True)
            for i,im in enumerate(prepared['images']):
                source=hevfm/im['image']; image_id=f'input-{i:02d}'
                dest=images_dir/f'{image_id}.webp'
                with Image.open(source) as photo:
                    thumb=photo.convert('RGB');thumb.thumbnail((384,216));thumb.save(dest,format='WEBP',quality=85,method=6)
                thumbnails[i]=np.array(thumb)
                role=im['role']; role_index=i if role=='wrist' else raw_fixed
                after_index=i if role=='wrist' else fixed_ids.index(im['camera_index'])
                label_image=f'Wrist {i+1:02d}' if role=='wrist' else f'Fixed {after_index+1} · frame {raw_fixed % 5+1}'
                entry={'id':image_id,'index':i,'role':role,'camera_index':im['camera_index'],'label':label_image,'image':str(dest.relative_to(ROOT/'docs')),'raw_node':f'/Raw/{role}/{role_index}','ours_node':f'/Ours/{role}/{after_index}'}
                record['inputs'].append(entry)
                audit['input_images'].append({'index':i,'source':im['image'],'source_sha256':digest(source),'export':entry['image'],'export_sha256':digest(dest)})
                if role=='fixed': raw_fixed+=1
            for method in ('Raw','Ours'):
                for role in ('wrist','fixed'):
                    for i,pose in enumerate(states[method][role]):
                        image_index=i if role=='wrist' else (15+i if method=='Raw' else next(j for j,im in enumerate(prepared['images']) if im['role']=='fixed' and im['camera_index']==fixed_ids[i]))
                        im=prepared['images'][image_index];width,height=im['size'];fov_cam=float(2*np.arctan(height/(2*np.asarray(im['K'])[1,1])))
                        pose=np.asarray(pose);name=f'/{method}/{role}/{i}'
                        qwxyz=vtf.SO3.from_matrix(pose[:3,:3]).wxyz
                        server.scene.add_camera_frustum(name,fov=fov_cam,aspect=width/height,scale=frustum_size,color=PALETTE[role],line_width=2.8*capture['settings'].get('frustum_line_width_scale',1) if physical else 2.8,image=thumbnails[image_index],wxyz=qwxyz,position=pose[:3,3])
                        seg=frustum_segments(fov_cam,width/height,frustum_size*1.04)
                        # Overlay shares the frustum's parent transform.
                        server.scene.add_line_segments(name+'/selected',points=seg.astype(np.float32),colors=(190,35,128),line_width=5,visible=False)
                        server.scene.add_label(name+'/selected/label',text=f'{role.title()} {i+1}',position=(0,0,0))
            server.scene.add_frame('/ready',show_axes=False,visible=False)
            payload=server.get_scene_serializer().serialize()
            file_path=output/f'{slug}.viser';file_path.write_bytes(payload)
            record['file']={'path':str(file_path.relative_to(ROOT/'docs')),'bytes':len(payload)}
            audit['export']={'path':record['file']['path'],'sha256':digest(file_path),'bytes':len(payload)}
        finally:
            server.stop()
        public['scenes'].append(record);provenance['cases'].append(audit)
        print(f'{slug}: {len(points):,} points, {len(record["inputs"])} inputs, {len(payload)/1e6:.1f} MB',flush=True)
    (ROOT/'docs/assets/data/scenes.json').write_text(json.dumps(public,indent=2)+'\n')
    (ROOT/'tools/scene-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hevfm',type=Path,default=ROOT.parent/'HEVFM')
    args=parser.parse_args();export(args.hevfm.resolve())
