from project import ROOT, WORK, BUILD, CONFIG, PACKAGE, adb_args
"""Bounded HTTP Range access to a single uncompressed Google Play asset slice.

No large APK is stored on the computer. Extracted entries are verified by
ZIP CRC and, at import time, the original Android Octo MD5.
"""
import io

import googleplay_probe as p
from gplaydl.protobuf import ProtoDecoder


class RemotePlayZip(io.RawIOBase):
    def __init__(self, pack, budget_mb=32):
        info = p.api._navigate((p.PRIVATE / f'{pack}-asset-response.pb').read_bytes(), 1, 151)
        modules = p.api._all_bytes(info, 3)
        if len(modules) != 1:
            raise ValueError('Expected one asset module')
        module = ProtoDecoder(modules[0]).read_all_ordered()
        if p.api._first_string(module, 1) != pack:
            raise ValueError('Asset module name mismatch')
        slices = p.api._all_bytes(module, 3)
        if len(slices) != 1:
            raise ValueError('Expected a single asset slice')
        sf = ProtoDecoder(slices[0]).read_all_ordered()
        full = ProtoDecoder(p.api._first_bytes(sf, 2)).read_all_ordered()
        chunks = p.api._all_bytes(full, 4)
        if len(chunks) != 1 or (p.api._first_int(full, 3) or 0) != 0:
            raise ValueError('Only uncompressed single-chunk slices support range access')
        chunk = ProtoDecoder(chunks[0]).read_all_ordered()
        self.url = p.api._first_string(chunk, 3)
        self.size = p.api._first_int(chunk, 1)
        self.position = 0
        self.block_size = 65536
        self.cache = {}
        self.prefetched = []
        self.transferred = 0
        self.budget = budget_mb * 1024**2
        self.client = p.httpx.Client(follow_redirects=True, timeout=45)

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        target = offset if whence == 0 else self.position + offset if whence == 1 else self.size + offset
        if target < 0:
            raise ValueError('Negative file position')
        self.position = target
        return target

    def block(self, index):
        if index in self.cache:
            return self.cache[index]
        start = index * self.block_size
        end = min(self.size, start + self.block_size) - 1
        result = self.fetch_range(start, end)
        self.cache[index] = result
        return result

    def fetch_range(self, start, end):
        for offset, data in self.prefetched:
            if offset <= start and end < offset + len(data):
                return data[start - offset:end - offset + 1]
        if self.transferred + end - start + 1 > self.budget:
            raise ValueError('Range download exceeds configured transfer budget')
        with self.client.stream('GET', self.url, headers={
                'Range': f'bytes={start}-{end}', 'Accept-Encoding': 'identity'}) as response:
            if response.status_code != 206:
                raise ValueError(f'CDN did not honor byte range (HTTP {response.status_code})')
            if response.headers.get('Content-Range') != f'bytes {start}-{end}/{self.size}':
                raise ValueError('CDN Content-Range mismatch')
            result = bytearray()
            for data in response.iter_bytes():
                result.extend(data)
                if len(result) > end - start + 1:
                    raise ValueError('CDN returned more bytes than requested')
        if len(result) != end - start + 1:
            raise ValueError('Truncated HTTP range')
        self.transferred += len(result)
        return bytes(result)

    def prefetch_entries(self, entries):
        ranges = []
        for entry in entries:
            start = entry.header_offset
            end = min(self.size - 1, start + 30 + len(entry.filename.encode('utf-8'))
                      + len(entry.extra) + entry.compress_size + 4096)
            if ranges and start <= ranges[-1][1] + 65536:
                ranges[-1][1] = max(ranges[-1][1], end)
            else:
                ranges.append([start, end])
        required = sum(end - start + 1 for start, end in ranges)
        if self.transferred + required > self.budget:
            raise ValueError('Selected entry ranges exceed the transfer budget')
        for start, end in ranges:
            self.prefetched.append((start, self.fetch_range(start, end)))

    def read(self, size=-1):
        if size < 0:
            size = self.size - self.position
        remaining = min(size, self.size - self.position)
        # ZIP readers request the entire central directory in one read.
        # Preserve that range instead of issuing dozens of small HTTP calls.
        if remaining > self.block_size:
            result = self.fetch_range(self.position, self.position + remaining - 1)
            self.position += len(result)
            return result
        output = bytearray()
        while remaining > 0:
            index, inside = divmod(self.position, self.block_size)
            data = self.block(index)
            take = min(remaining, len(data) - inside)
            if take <= 0:
                raise ValueError('Invalid range block')
            output.extend(data[inside:inside + take])
            self.position += take
            remaining -= take
        return bytes(output)

    def close(self):
        if not self.closed:
            self.client.close()
        super().close()
