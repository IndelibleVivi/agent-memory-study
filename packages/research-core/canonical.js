/* AMS JSON canonical v1. This is deterministic, not RFC 8785. */
import {CONTENT_FIELDS} from "./content-fields.generated.js";
export {CONTENT_FIELDS};
export function canonicalValue(value) {
  if (value === null) return "null";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new Error("canonicalValue: non-finite number");
    if (!Number.isSafeInteger(value)) throw new Error("canonicalValue: v1 supports integers only");
    return String(value);
  }
  if (typeof value === "string") return asciiJsonString(value);
  if (Array.isArray(value)) return `[${value.map(canonicalValue).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort(compareCodePoints).map(key => `${asciiJsonString(key)}:${canonicalValue(value[key])}`).join(",")}}`;
  }
  throw new Error("canonicalValue: unsupported JSON value");
}

function compareCodePoints(a, b) {
  const left = Array.from(a, c => c.codePointAt(0)), right = Array.from(b, c => c.codePointAt(0));
  for (let i = 0; i < Math.min(left.length, right.length); i++) {
    if (left[i] !== right[i]) return left[i] - right[i];
  }
  return left.length - right.length;
}

function asciiJsonString(value) {
  return JSON.stringify(value).replace(
    /[^\x20-\x7e]/g,
    character => `\\u${character.charCodeAt(0).toString(16).padStart(4, "0")}`,
  );
}

export function canonicalObjectBytes(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("canonicalObjectBytes: expected an object");
  }
  return utf8(canonicalValue(value));
}

export function contentFieldsFor(record) {
  if (!record || typeof record !== "object" || Array.isArray(record)) {
    throw new Error("contentFieldsFor: expected an object");
  }
  const fields = CONTENT_FIELDS[record.kind];
  if (!fields) throw new Error(`contentFieldsFor: unsupported kind ${String(record.kind)}`);
  return fields.filter(field => Object.hasOwn(record, field)).sort();
}

export function contentFields(record, fields) {
  if (!record || typeof record !== "object" || Array.isArray(record)) {
    throw new Error("contentFields: expected an object");
  }
  return [...fields].filter(field => Object.hasOwn(record, field)).sort();
}

export async function contentDigest(record, fields = contentFieldsFor(record)) {
  const names = contentFields(record, fields);
  const payload = Object.fromEntries(names.map(field => [field, record[field]]));
  return {
    algorithm: "sha256",
    value: await sha256Hex(canonicalObjectBytes(payload)),
    canonicalization: "ams-json-canonical/1",
    fields: names,
  };
}

function utf8(value) {
  return new TextEncoder().encode(value);
}

async function sha256Hex(bytes) {
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map(byte => byte.toString(16).padStart(2, "0")).join("");
}
