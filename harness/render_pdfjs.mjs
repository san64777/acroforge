// usage: node render_pdfjs.mjs <in.pdf> <out.png> [pageIndex=0] [scale=2]
// Pre-set canvas globals BEFORE pdfjs-dist loads so its polyfill check is a no-op
import { createCanvas, Path2D, DOMMatrix, ImageData } from "@napi-rs/canvas";
globalThis.Path2D = Path2D;
globalThis.DOMMatrix = DOMMatrix;
globalThis.ImageData = ImageData;

import { getDocument, AnnotationMode } from "pdfjs-dist/legacy/build/pdf.mjs";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join, dirname } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const PDFJS_DIR = join(__dirname, "node_modules", "pdfjs-dist");
const cMapUrl = join(PDFJS_DIR, "cmaps") + "/";
const standardFontDataUrl = join(PDFJS_DIR, "standard_fonts") + "/";

const [, , input, output, pageArg = "0", scaleArg = "2"] = process.argv;
const data = new Uint8Array(readFileSync(input));
const doc = await getDocument({
  data,
  isEvalSupported: false,
  cMapUrl,
  cMapPacked: true,
  standardFontDataUrl,
}).promise;
const page = await doc.getPage(Number(pageArg) + 1); // pdf.js is 1-indexed
const viewport = page.getViewport({ scale: Number(scaleArg) });
const canvas = createCanvas(Math.ceil(viewport.width), Math.ceil(viewport.height));
const ctx = canvas.getContext("2d");
await page.render({
  canvasContext: ctx,
  viewport,
  annotationMode: AnnotationMode.ENABLE,
}).promise;
writeFileSync(output, canvas.toBuffer("image/png"));
