/**
 * Generate the PWA icons.
 *
 *   node scripts/make-icons.mjs
 *
 * Written by hand rather than pulled from an image library because the icon is four
 * rectangles and a diagonal, and adding a native-dependency image toolchain to a container
 * build to draw that would be a poor trade. Node's own zlib does the compression, so this
 * has no dependencies at all and the output is byte-reproducible.
 *
 * The mark: a rising bar chart in the carbon-intensity ramp — the same green-to-red scale
 * the UI uses for a grid going from clean to dirty.
 */

import { deflateSync } from "node:zlib";
import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const OUT = join(dirname(fileURLToPath(import.meta.url)), "..", "public");

const BACKGROUND = [11, 18, 32, 255]; // #0b1220, the app's ground
const BARS = [
  [0.18, 0.42, [74, 222, 128, 255]], //  clean   — green
  [0.34, 0.58, [163, 230, 53, 255]],
  [0.5, 0.72, [250, 204, 21, 255]],
  [0.66, 0.88, [248, 113, 113, 255]], //  dirty   — red
];

const CRC_TABLE = Uint32Array.from({ length: 256 }, (_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});

function crc32(buf) {
  let c = 0xffffffff;
  for (const byte of buf) c = CRC_TABLE[(c ^ byte) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

function chunk(type, data) {
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body));
  return Buffer.concat([length, body, crc]);
}

function png(size) {
  // One RGBA pixel buffer, filled by painting rectangles. At 512x512 this is a megabyte
  // of scratch memory for a fraction of a second; simplicity wins over cleverness.
  const pixels = Buffer.alloc(size * size * 4);
  for (let i = 0; i < size * size; i++) pixels.set(BACKGROUND, i * 4);

  const paint = (x0, y0, x1, y1, rgba) => {
    for (let y = Math.round(y0); y < Math.round(y1); y++) {
      for (let x = Math.round(x0); x < Math.round(x1); x++) {
        if (x < 0 || y < 0 || x >= size || y >= size) continue;
        pixels.set(rgba, (y * size + x) * 4);
      }
    }
  };

  const baseline = size * 0.8;
  for (const [left, right, colour] of BARS) {
    const height = (right - 0.18) * 0.62 + 0.1;
    paint(size * left, baseline - size * height, size * right * 0.98, baseline, colour);
  }
  // A ground line, so the mark reads as a chart rather than as loose blocks.
  paint(size * 0.14, baseline, size * 0.9, baseline + Math.max(2, size * 0.018), [
    100, 116, 139, 255,
  ]);

  // PNG scanlines are each prefixed with a filter byte; 0 means "none".
  const raw = Buffer.alloc(size * (size * 4 + 1));
  for (let y = 0; y < size; y++) {
    raw[y * (size * 4 + 1)] = 0;
    pixels.copy(raw, y * (size * 4 + 1) + 1, y * size * 4, (y + 1) * size * 4);
  }

  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(size, 0);
  ihdr.writeUInt32BE(size, 4);
  ihdr[8] = 8; // bit depth
  ihdr[9] = 6; // colour type: RGBA
  // 10-12: compression, filter and interlace methods, all 0.

  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", ihdr),
    chunk("IDAT", deflateSync(raw, { level: 9 })),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="12" fill="#0b1220"/>
  <rect x="11" y="34" width="9" height="18" fill="#4ade80"/>
  <rect x="22" y="28" width="9" height="24" fill="#a3e635"/>
  <rect x="33" y="22" width="9" height="30" fill="#facc15"/>
  <rect x="44" y="15" width="9" height="37" fill="#f87171"/>
  <rect x="9" y="52" width="46" height="3" fill="#64748b"/>
</svg>
`;

mkdirSync(OUT, { recursive: true });
writeFileSync(join(OUT, "favicon.svg"), svg);
for (const size of [192, 512]) {
  writeFileSync(join(OUT, `icon-${size}.png`), png(size));
  console.log(`wrote public/icon-${size}.png`);
}
console.log("wrote public/favicon.svg");
