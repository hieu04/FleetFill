// Decrypt and decode a copied ETS2/ATS SII save into a plaintext research file.
// Never modifies the source file.
import { writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { SIIDecryptor } from "@trucky/sii-decrypt-ts";

const [, , inputArgument, outputArgument] = process.argv;
if (!inputArgument || !outputArgument) {
  console.error("Usage: node decrypt-save.mjs <input-sii> <output-text>");
  process.exit(2);
}

const inputPath = resolve(inputArgument);
const outputPath = resolve(outputArgument);
const result = SIIDecryptor.decrypt(inputPath, true);
if (!result.success || !result.data) {
  console.error(`SII decode failed: ${result.error ?? "unknown error"}`);
  process.exit(3);
}
if (!result.data.subarray(0, 8).equals(Buffer.from("SiiNunit"))) {
  console.error("SII decoder did not produce a valid text SII document");
  process.exit(4);
}

writeFileSync(outputPath, result.data);
console.log(`DECODED_SAVE_COPY: ${outputPath}`);
console.log(`SOURCE_TYPE: ${result.type}`);
console.log(`SOURCE_ENCRYPTED: ${Boolean(result.encrypted)}`);
console.log(`PLAINTEXT_BYTES: ${result.data.length}`);
