#!/usr/bin/env python3
"""Generate the TypeScript material model from spec/material-schema.json.

The JSON file is the source of truth.  Normal invocation writes
sim/src/material/model.ts; ``--check`` verifies that the checked-in file is
byte-identical to a fresh generation.  The design allowlist is checked against
the ``Params`` interface in sim/src/params.ts (parsed with a regex), so a
renamed or removed legacy key fails here instead of in the browser.  Only
Python's standard library is used.  There is no C++ output: firmware receives
the derived legacy Params, never a material.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "spec" / "material-schema.json"
PARAMS_PATH = ROOT / "sim" / "src" / "params.ts"
TS_PATH = ROOT / "sim" / "src" / "material" / "model.ts"

REQUIRED = ("key", "label", "unit", "default", "min", "max", "step", "group", "help")
OPTIONAL = ("integer", "log", "options")
DESIGN_TYPES = ("number", "string", "boolean")


def params_fields() -> dict[str, str]:
    """Key -> TypeScript type text of every field of `export interface Params { ... }`."""
    source = PARAMS_PATH.read_text(encoding="utf-8")
    match = re.search(r"^export interface Params \{\n(.*?)^\}", source, re.MULTILINE | re.DOTALL)
    if not match:
        raise ValueError(f"cannot find `export interface Params {{` in {PARAMS_PATH.relative_to(ROOT)}")
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        code = line.split("//", 1)[0].strip()
        if not code:
            continue
        field = re.fullmatch(r"(\w+)\s*:\s*([^;]+?)\s*;", code)
        if not field:
            raise ValueError(f"cannot parse Params interface line: {line.strip()!r}")
        fields[field.group(1)] = field.group(2)
    if not fields:
        raise ValueError("Params interface parsed as empty")
    return fields


def load_schema() -> tuple[dict[str, Any], list[dict[str, Any]], list[str], str]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    if not isinstance(schema, dict):
        raise ValueError("material schema must be an object")
    version = schema.get("version")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise ValueError("material schema version must be a positive integer")
    fields = schema.get("fields")
    if not isinstance(fields, list) or not fields:
        raise ValueError("material schema must contain a non-empty fields array")
    keys: set[str] = set()
    for field in fields:
        if not isinstance(field, dict) or any(name not in field for name in REQUIRED):
            raise ValueError("each material field needs " + ", ".join(REQUIRED))
        key = field["key"]
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z_]\w*", key) or key in keys:
            raise ValueError(f"invalid or duplicate material field key: {key!r}")
        keys.add(key)
        extra = sorted(set(field) - set(REQUIRED) - set(OPTIONAL))
        if extra:
            raise ValueError(f"{key}: unknown attribute(s) {', '.join(extra)}")
        for name in ("label", "unit", "group", "help"):
            if not isinstance(field[name], str):
                raise ValueError(f"{key}.{name} must be a string")
        for name in ("default", "min", "max", "step"):
            value = field[name]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{key}.{name} must be numeric")
        if field["min"] > field["max"] or not field["min"] <= field["default"] <= field["max"]:
            raise ValueError(f"invalid range/default for {key}")
        if field["step"] <= 0:
            raise ValueError(f"{key}.step must be positive")
        for name in ("integer", "log"):
            if name in field and not isinstance(field[name], bool):
                raise ValueError(f"{key}.{name} must be a boolean")
        integer = field.get("integer", False)
        if integer and any(float(field[name]) != int(field[name]) for name in ("default", "min", "max", "step")):
            raise ValueError(f"integer field {key} has a non-integer bound/default/step")
        if "options" in field:
            options = field["options"]
            if not integer:
                raise ValueError(f"{key}.options is only allowed on an integer field")
            if not isinstance(options, list) or any(not isinstance(o, str) or not o for o in options):
                raise ValueError(f"{key}.options must be an array of non-empty strings")
            want = int(field["max"]) - int(field["min"]) + 1
            if len(options) != want:
                raise ValueError(f"{key}.options has {len(options)} entries, max - min + 1 = {want}")
            if len(set(options)) != len(options):
                raise ValueError(f"{key}.options has duplicate entries")

    design = schema.get("design")
    if not isinstance(design, dict) or not isinstance(design.get("allow"), list) or not design["allow"]:
        raise ValueError("material schema needs design.allow, a non-empty array of Params keys")
    allow = design["allow"]
    if any(not isinstance(k, str) for k in allow) or len(set(allow)) != len(allow):
        raise ValueError("design.allow must hold unique strings")
    params = params_fields()
    unknown = [k for k in allow if k not in params]
    if unknown:
        raise ValueError(f"design.allow key(s) not in Params ({PARAMS_PATH.relative_to(ROOT)}): {', '.join(unknown)}")
    untyped = [f"{k}: {params[k]}" for k in allow if params[k] not in DESIGN_TYPES]
    if untyped:
        raise ValueError(f"design.allow key(s) not number/string/boolean in Params: {', '.join(untyped)}")

    canonical = json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return schema, fields, allow, digest


def js(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def number(value: Any) -> str:
    """Stable source spelling for a JSON numeric value."""
    if isinstance(value, int):
        return str(value)
    result = format(float(value), ".15g")
    if result == "-0":
        return "0"
    return result


# Hand-written part of model.ts: validators, envelope and migration.  A new schema
# version adds a `case` to migrateMaterial below and regenerates.
TAIL = r'''
export const MATERIAL_ENVELOPE_KIND = "liquid-watch-material" as const;

/** Where a preset's property value comes from (docs/physical-renderer.md, "Provenance of preset values"). */
export type Provenance = "measured" | "estimated" | "artistic";
export const PROVENANCE_VALUES: readonly Provenance[] = ["measured", "estimated", "artistic"];
export type MaterialProvenance = Partial<Record<MaterialKey, Provenance>>;

/** A material file: the material, the allowlisted design keys and optional name / per-property provenance. */
export interface MaterialEnvelope {
  readonly kind: typeof MATERIAL_ENVELOPE_KIND;
  readonly version: typeof MATERIAL_VERSION;
  readonly name?: string;
  readonly material: Material;
  readonly design: Design;
  readonly provenance?: MaterialProvenance;
}

const ENVELOPE_KEYS: readonly string[] = ["kind", "version", "name", "material", "design", "provenance"];
const HEX_COLOUR = /^#[0-9a-f]{6}$/i;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasOwn(value: Record<string, unknown>, key: string): boolean {
  return Object.prototype.hasOwnProperty.call(value, key);
}

function isMaterialKey(key: string): key is MaterialKey {
  return (MATERIAL_KEYS as readonly string[]).includes(key);
}

function isDesignKey(key: string): key is DesignKey {
  return (DESIGN_KEYS as readonly string[]).includes(key);
}

function fail(what: string, message: string): never {
  throw new Error(`Invalid ${what}: ${message}`);
}

/** Validate a complete material: exactly the schema's keys, each finite, in range and integer where flagged. */
export function validateMaterial(value: unknown): Material {
  if (!isRecord(value)) fail("material", "expected an object");
  const unknown = Object.keys(value).filter((key) => !isMaterialKey(key));
  if (unknown.length) fail("material", `unknown field(s) ${unknown.join(", ")}`);
  const result = {} as Material;
  for (const meta of MATERIAL_META) {
    if (!hasOwn(value, meta.key)) fail("material", `missing field ${meta.key}`);
    const raw = value[meta.key];
    if (typeof raw !== "number" || !Number.isFinite(raw)) fail("material", `${meta.key} must be a finite number`);
    if (raw < meta.min || raw > meta.max) fail("material", `${meta.key} = ${raw} must be in [${meta.min}, ${meta.max}]`);
    if (meta.integer && !Number.isInteger(raw)) fail("material", `${meta.key} = ${raw} must be an integer`);
    result[meta.key] = raw;
  }
  return result;
}

/** Validate a (partial) design: only allowlisted Params keys, each of its Params type; strings are #rrggbb colours. */
export function validateDesign(value: unknown): Design {
  if (!isRecord(value)) fail("design", "expected an object");
  const bad = Object.keys(value).filter((key) => !isDesignKey(key));
  if (bad.length) fail("design", `key(s) not in the design allowlist (derived from the material or fixed): ${bad.join(", ")}`);
  const result: Record<string, unknown> = {};
  for (const key of DESIGN_KEYS) {
    if (!hasOwn(value, key)) continue;
    const raw = value[key];
    const want = typeof DEFAULT_PARAMS[key];
    if (typeof raw !== want) fail("design", `${key} must be a ${want}`);
    if (typeof raw === "number" && !Number.isFinite(raw)) fail("design", `${key} must be finite`);
    if (typeof raw === "string" && !HEX_COLOUR.test(raw)) fail("design", `${key} = ${JSON.stringify(raw)} must be a #rrggbb colour`);
    result[key] = raw;
  }
  return result as Design;
}

function validateProvenance(value: unknown): MaterialProvenance {
  if (!isRecord(value)) fail("provenance", "expected an object");
  const result: MaterialProvenance = {};
  const unknown = Object.keys(value).filter((key) => !isMaterialKey(key));
  if (unknown.length) fail("provenance", `unknown material field(s) ${unknown.join(", ")}`);
  for (const key of MATERIAL_KEYS) {
    if (!hasOwn(value, key)) continue;
    const raw = value[key];
    if (!(PROVENANCE_VALUES as readonly unknown[]).includes(raw)) fail("provenance", `${key} must be one of ${PROVENANCE_VALUES.join(", ")}`);
    result[key] = raw as Provenance;
  }
  return result;
}

/** Copy of an object with only the keys `keep` accepts; for explicit migration steps only. */
export function keepKeys(value: unknown, keep: (key: string) => boolean): unknown {
  if (!isRecord(value)) return value;
  const result: Record<string, unknown> = {};
  for (const key of Object.keys(value)) if (keep(key)) result[key] = value[key];
  return result;
}

/**
 * Bring a material envelope of any supported version to MATERIAL_VERSION, unvalidated. Each `case`
 * upgrades one version in place; a key is dropped only by the explicit step of the version that removed
 * it. A current-version file is passed through untouched, so the strict validators reject any key the
 * schema does not know (envelope, material, provenance) instead of losing it silently.
 */
export function migrateMaterial(o: Record<string, unknown>): Record<string, unknown> {
  const from = o.version;
  if (typeof from !== "number" || !Number.isInteger(from) || from < 1) fail("material file", `unsupported version ${JSON.stringify(from)}`);
  if (from > MATERIAL_VERSION) fail("material file", `version ${from} is newer than this simulator (${MATERIAL_VERSION})`);
  const r: Record<string, unknown> = { ...o };
  if (isRecord(r.material)) r.material = { ...r.material };
  for (let v = from; v < MATERIAL_VERSION; v++) {
    switch (v) {
      case 1: {
        // version 1 → 2: the design key digitParallax (px per g of absolute tilt, behind liquid only) gave way to the
        // view-angle rear parallax rearParallax (rear wall depth, px). Not a unit conversion: the old value is dropped
        // and a design that set one takes the new default explicitly.
        if (isRecord(r.design) && hasOwn(r.design, "digitParallax")) {
          r.design = { ...keepKeys(r.design, (key) => key !== "digitParallax") as Record<string, unknown>, rearParallax: DEFAULT_PARAMS.rearParallax };
        }
        break;
      }
      default:
        fail("material file", `no migration from version ${v}`);
    }
  }
  r.version = MATERIAL_VERSION;
  return r;
}

/** Parse and validate a material file (JSON text or an already parsed object). Legacy Params exports are rejected. */
export function parseMaterialEnvelope(input: unknown): MaterialEnvelope {
  let value = input;
  if (typeof input === "string") {
    try { value = JSON.parse(input); } catch (error) { fail("material file", `not JSON (${(error as Error).message})`); }
  }
  if (!isRecord(value)) fail("material file", "expected a JSON object");
  if (hasOwn(value, "v") && hasOwn(value, "liquid")) {
    throw new Error("This is a legacy Params export (it has `v` and `liquid`), not a material file; legacy configs are rejected.");
  }
  if (value.kind !== MATERIAL_ENVELOPE_KIND) fail("material file", `kind must be "${MATERIAL_ENVELOPE_KIND}" (got ${JSON.stringify(value.kind)})`);
  const o = migrateMaterial(value);
  const unknown = Object.keys(o).filter((key) => !ENVELOPE_KEYS.includes(key));
  if (unknown.length) fail("material file", `unknown field(s) ${unknown.join(", ")}`);
  if (hasOwn(o, "name") && typeof o.name !== "string") fail("material file", "name must be a string");
  return {
    kind: MATERIAL_ENVELOPE_KIND,
    version: MATERIAL_VERSION,
    ...(typeof o.name === "string" ? { name: o.name } : {}),
    material: validateMaterial(o.material),
    design: validateDesign(o.design),
    ...(hasOwn(o, "provenance") ? { provenance: validateProvenance(o.provenance) } : {}),
  };
}

/** Validate and write a material file: canonical key order, 2-space JSON, trailing newline. */
export function serializeMaterialEnvelope(env: { material: Material; design: Design; name?: string; provenance?: MaterialProvenance }): string {
  const parsed = parseMaterialEnvelope({ ...env, kind: MATERIAL_ENVELOPE_KIND, version: MATERIAL_VERSION });
  return JSON.stringify(parsed, null, 2) + "\n";
}
'''


def generate_ts(schema: dict[str, Any], fields: list[dict[str, Any]], allow: list[str], digest: str) -> str:
    version = schema["version"]
    keys = [field["key"] for field in fields]
    lines = [
        "// GENERATED by sim/tools/gen_material.py — do not edit.",
        f"// Source: spec/material-schema.json (schema {version}, {digest})",
        "",
        "import type { Params } from \"../params\";",
        "import { DEFAULT_PARAMS } from \"../params\";",
        "",
        f"export const MATERIAL_VERSION = {version} as const;",
        f"export const MATERIAL_SCHEMA_DIGEST = {js(digest)} as const;",
        "",
        "/** Physical material, vessel and lighting properties (units and bounds in MATERIAL_META). */",
        "export interface Material {",
    ]
    lines.extend(f"  {key}: number;" for key in keys)
    lines.extend(
        [
            "}",
            "",
            "export type MaterialKey = keyof Material;",
            "",
            "export interface MaterialFieldMeta {",
            "  readonly key: MaterialKey;",
            "  readonly label: string;",
            "  readonly unit: string;",
            "  readonly min: number;",
            "  readonly max: number;",
            "  readonly step: number;",
            "  readonly group: string;",
            "  readonly help: string;",
            "  readonly integer: boolean;",
            "  /** Slider moves in log space (the range spans decades). */",
            "  readonly log: boolean;",
            "  /** Integer enum labels, options[value - min]. */",
            "  readonly options?: readonly string[];",
            "}",
            "",
            "export const DEFAULT_MATERIAL: Material = {",
        ]
    )
    lines.extend(f"  {field['key']}: {number(field['default'])}," for field in fields)
    lines.extend(["};", "", "export const MATERIAL_META: readonly MaterialFieldMeta[] = ["])
    for field in fields:
        options = f", options: {js(field['options'])}" if "options" in field else ""
        lines.append(
            "  { key: %s, label: %s, unit: %s, min: %s, max: %s, step: %s, group: %s, help: %s, integer: %s, log: %s%s },"
            % (
                js(field["key"]),
                js(field["label"]),
                js(field["unit"]),
                number(field["min"]),
                number(field["max"]),
                number(field["step"]),
                js(field["group"]),
                js(field["help"]),
                "true" if field.get("integer", False) else "false",
                "true" if field.get("log", False) else "false",
                options,
            )
        )
    lines.extend(
        [
            "];",
            "",
            f"export const MATERIAL_KEYS: readonly MaterialKey[] = {js(keys)};",
            "",
            "/** Legacy Params keys a material file may set directly (schema design.allow); every other key is derived. */",
            "export const DESIGN_KEYS = [",
        ]
    )
    lines.extend(f"  {js(key)}," for key in allow)
    lines.extend(
        [
            "] as const satisfies readonly (keyof Params)[];",
            "",
            "export type DesignKey = (typeof DESIGN_KEYS)[number];",
            "export type Design = Partial<Pick<Params, DesignKey>>;",
        ]
    )
    return "\n".join(lines) + "\n" + TAIL


def main() -> int:
    check = len(sys.argv) == 2 and sys.argv[1] == "--check"
    if len(sys.argv) > 1 and not check:
        print("usage: gen_material.py [--check]", file=sys.stderr)
        return 2
    try:
        schema, fields, allow, digest = load_schema()
        content = generate_ts(schema, fields, allow, digest)
        existing = TS_PATH.read_text(encoding="utf-8") if TS_PATH.exists() else None
        if check:
            if existing != content:
                print(f"generated file is out of date: {TS_PATH.relative_to(ROOT)} (run npm run gen:material)", file=sys.stderr)
                return 1
            print("material schema generated file is up to date")
            return 0
        TS_PATH.parent.mkdir(parents=True, exist_ok=True)
        TS_PATH.write_text(content, encoding="utf-8")
        print("wrote", TS_PATH.relative_to(ROOT))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"gen_material.py: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
