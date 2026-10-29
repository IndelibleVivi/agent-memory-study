export type PublicKind = "material" | "study" | "question" | "finding";
export type EntityKind =
  | "capture" | "source_work" | "source_revision" | "source_note"
  | "artifact" | "extraction" | "read_activity" | "excerpt"
  | "entry" | "claim_revision" | "thread" | "session"
  | "relation_proposal" | "evidence_relation" | "support_bundle"
  | "observation" | "design" | "run" | "analysis" | "changeset"
  | "publication_manifest";

export interface EntityRef { kind: EntityKind; id: string; revision: string; }
export interface CurrentRef { kind: EntityKind; id: string; selection: "current"; }
export interface PublicObject {
  kind: EntityKind; id: string; revision: string; public_kind: PublicKind;
  public_id: string;
  route: string; shard: string; revision_shard: string; packet_v2: string;
}
export interface Packet {
  schema: "ams-study-packet/2"; kind: PublicKind; id: string; title: string;
  entity_refs: EntityRef[]; attribution: Record<string, unknown>;
  content: Record<string, unknown>;
  manifest: Array<{kind: PublicKind; id: string; revision: string;
    publicKind: PublicKind; title: string; url: string}>;
  manifest_policy: string;
}
export interface PublicCorpusManifest {
  schema: "ams-public-corpus-manifest/1";
  contract_version: "ams-core/2";
  compiler_version: "ams-content-compiler/2";
  canonicalization: "ams-json-canonical/1";
  record_shards: string[];
  objects: PublicObject[];
  routes: Record<"home" | PublicKind, string | string[]>;
  graphs: {
    navigation_memberships: unknown[];
    references: Array<{from: string; to: string; relation: string; locator: string}>;
    arguments: unknown[];
  };
}

export const CONTRACT_VERSION: "ams-core/2";
export const COMPILER_VERSION: "ams-content-compiler/2";
export const PACKET_VERSION: "ams-study-packet/2";
export const COLLECTION_VERSION: "ams-study-collection/2";
export const PUBLIC_MANIFEST_VERSION: "ams-public-corpus-manifest/1";
export function entityRef(record: Record<string, unknown>): EntityRef;
export function refKey(ref: EntityRef): string;
export function publicRef(kind: PublicKind, id: string, revision?: string | null): EntityRef | {kind: EntityKind; id: string};
export function referenceGraph(manifest: PublicCorpusManifest): unknown;
export function navigationOf(manifest: PublicCorpusManifest): unknown[];
export function argumentOf(manifest: PublicCorpusManifest): unknown[];
export function impact(manifest: PublicCorpusManifest, kind: PublicKind, id: string): unknown;
export function packet(manifest: PublicCorpusManifest, kind: PublicKind, id: string, loaded?: Record<string, unknown> | Packet): Packet;
export function objectFor(manifest: PublicCorpusManifest, kind: PublicKind, id: string): PublicObject;
export function objectShardPath(manifest: PublicCorpusManifest, kind: PublicKind, id: string): string;
export function packetShardPath(manifest: PublicCorpusManifest, kind: PublicKind, id: string): string;
export function revisionShardPath(manifest: PublicCorpusManifest, kind: PublicKind, id: string): string;
export function packetFromShards(manifest: PublicCorpusManifest, kind: PublicKind, id: string, loaded: Record<string, unknown>): Packet;
export function collection(manifest: PublicCorpusManifest, refs: Array<{kind: PublicKind; id: string}>, loaded?: Record<string, unknown>): unknown;
export function packetPublicRoute(kind: PublicKind, id: string): string;
export { CONTENT_FIELDS, contentFieldsFor, contentDigest } from "./canonical.js";
