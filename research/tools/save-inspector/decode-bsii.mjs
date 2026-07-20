// Decode a copied BSII file to a separate plaintext file. Never edits input.
import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { BSIIDecoder, SignatureType } from "@trucky/sii-decrypt-ts";

const [, , inputArgument, outputArgument] = process.argv;
if (!inputArgument || !outputArgument) {
  console.error("Usage: node decode-bsii.mjs <input-bsii> <output-text>");
  process.exit(2);
}

const inputPath = resolve(inputArgument);
const outputPath = resolve(outputArgument);
const input = readFileSync(inputPath);
if (input.length < 8 || input.readUInt32LE(0) !== SignatureType.Binary) {
  console.error(`Input is not BSII: ${inputPath}`);
  process.exit(3);
}

const result = BSIIDecoder.decode(input);
if (!result.success || !result.data.subarray(0, 8).equals(Buffer.from("SiiNunit"))) {
  console.error("BSII decoder did not produce a valid text SII document");
  process.exit(4);
}

writeFileSync(outputPath, result.data);
console.log(`DECODED_BSII_COPY: ${outputPath}`);
console.log(`BINARY_VERSION: ${result.header?.version}`);
console.log(`PLAINTEXT_BYTES: ${result.data.length}`);
