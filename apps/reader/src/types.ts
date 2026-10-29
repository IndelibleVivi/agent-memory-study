export type PublicKind = "material" | "study" | "question" | "finding";
export type Space = "continue" | "explore" | "library" | "lab";
export type EntityRef = {kind: string; id: string; revision: string};
export type Entity = EntityRef & {schema: string; state_revision: string; content_digest: unknown; [key: string]: any};
// The compatibility content is validated by the Python compiler. New research
// metadata remains extensible; it is never mixed with an imported private body.
export type Content = {id: string; title: string; [key: string]: any};
export type CatalogueItem = {kind: PublicKind; id: string; title: string; intro: string; byline: string; date: string;
  categories: string[]; failureSurfaces: string[]; domains: string[]; directions: string[]; noteDepth?: string;
  materialIds: string[]; shard: string; packet?:string; ref?: EntityRef; exercise?: string};
export type Bootstrap = {schema: "ams-reader/1"; base: string; portable: boolean; catalogue: CatalogueItem[];
  room: Content; atlas: Content; initial: {kind: PublicKind; item: Content} | null; graph: any;
  portableContent?: Record<string, Content>; recordIndex:Record<string,string>; portableRecords?:Record<string,Entity>; portablePackets?:Record<string,any>; searchIndex?:any[]; location: string};
export type Command = {schema: "ams-command/1"; kind: "command"; command_id: string; idempotency_key: string;
  operation: "create" | "update"; target: {kind: string; id: string}; actor: {kind: "human"; id: string};
  record: Entity; expected_revision?: string};
export type SaveStatus = "ephemeral" | "pending" | "committed" | "conflict" | "disconnected";
export type Capability = {mode: "public" | "local"; durable: boolean; jobs: boolean};
export type WorkspaceAdapter = {
  capabilities: Capability;
  list(kind?: string): Promise<Entity[]>;
  load(kind: string, id: string, revision?: string): Promise<Entity>;
  apply(command: Command): Promise<any>;
  applyUnit(commands: Command[]): Promise<any>;
  upload(bytes: Uint8Array): Promise<{digest: string; byte_length: number}>;
  blob(digest: string): Promise<Uint8Array>;
  export(roots: EntityRef[]): Promise<any>;
  checkCapacity?(record:Entity): void;
  request(path: string, body?: unknown): Promise<any>;
};
declare global {
  interface Window { __AMS_BOOTSTRAP__: Bootstrap; }
}
