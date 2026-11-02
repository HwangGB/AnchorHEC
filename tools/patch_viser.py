"""Version-guarded bridge to the locally bundled Viser 1.0.24 scene store.

Only the website copy is modified. Viser retains its Apache-2.0 license.
No rendering algorithms are replaced. The bridge changes visibility, point-cloud
similarity transform, selection overlays and the viewing camera via Viser state.
"""
import base64
import re
import zstandard


def patch_client(html):
    compressed = re.search(r'data-c="([^"]+)"', html)
    if compressed is None:
        raise RuntimeError('Unsupported Viser packaging')
    source = zstandard.ZstdDecompressor().decompress(base64.b64decode(compressed[1])).decode()
    old = 'useInitialCamera:u,mutable:l};return(r||a?.darkMode)'
    new = 'useInitialCamera:u,mutable:l};window.__anchorhecViewer=d;window.__anchorhecWorld=()=>ph(d);return(r||a?.darkMode)'
    if source.count(old) != 1:
        raise RuntimeError('Viser 1.0.24 bridge signature changed; review required')
    source = source.replace(old, new)
    data = base64.b64encode(zstandard.ZstdCompressor(level=3).compress(source.encode())).decode()
    html = html[:compressed.start(1)] + data + html[compressed.end(1):]
    html = re.sub(r'data-cs="\d+"', f'data-cs="{len(source.encode())}"', html, count=1)
    return html.replace('</body>', '<!-- AnchorHEC modification: local scene-selection bridge, 2026-11-02. -->\n<script src="anchorhec-bridge.js"></script></body>')
