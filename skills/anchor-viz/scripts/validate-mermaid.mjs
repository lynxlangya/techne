#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';

const LIMITS = {
  maxNodes: 15,
  maxParticipants: 8,
  maxMessages: 20,
  maxEntities: 12,
  maxRelationships: 20,
  maxStates: 12,
  maxTransitions: 20,
  maxTypes: 12,
  maxMemberLines: 30,
};

const TYPE_TO_KIND = {
  flowchart: 'architecture',
  graph: 'architecture',
  sequencediagram: 'interaction',
  erdiagram: 'data-model',
  'statediagram-v2': 'state-model',
  statediagram: 'state-model',
  classdiagram: 'type-structure',
};

const CANONICAL_TYPES = {
  flowchart: 'flowchart',
  graph: 'graph',
  sequencediagram: 'sequenceDiagram',
  erdiagram: 'erDiagram',
  'statediagram-v2': 'stateDiagram-v2',
  statediagram: 'stateDiagram',
  classdiagram: 'classDiagram',
};

const ID_SCAN_RE = /[A-Za-z_][\w.:-]*/g;
const WORD_CHAR_RE = /[A-Za-z0-9_]/;

class ProvenanceError extends Error {
  constructor(payload) {
    super('provenance validation failed');
    this.payload = payload;
  }
}

function usage() {
  console.error(`Usage: validate-mermaid.mjs <diagram.md|diagram.mmd> [options]

Options:
  --project PATH           Verify techne provenance against a project root
  --max-nodes N            Architecture top-level node limit (default 15)
  --grouped                Allow over-budget architecture via grouping
  --split                  Allow over-budget architecture via split diagrams
  --max-participants N     Sequence participant limit (default 8)
  --max-messages N         Sequence message limit (default 20)
  --max-entities N         ER entity limit (default 12)
  --max-relationships N    ER relationship limit (default 20)
  --max-states N           State count limit (default 12)
  --max-transitions N      State transition limit (default 20)
  --max-types N            Class/type count limit (default 12)
  --max-member-lines N     Class relationship/member line limit (default 30)`);
}

function parseArgs(argv) {
  const args = { ...LIMITS, grouped: false, split: false, file: null, project: null };
  const numeric = new Set(Object.keys(LIMITS).map((key) => `--${key.replace(/[A-Z]/g, (m) => `-${m.toLowerCase()}`)}`));
  const byFlag = {
    '--max-nodes': 'maxNodes',
    '--max-participants': 'maxParticipants',
    '--max-messages': 'maxMessages',
    '--max-entities': 'maxEntities',
    '--max-relationships': 'maxRelationships',
    '--max-states': 'maxStates',
    '--max-transitions': 'maxTransitions',
    '--max-types': 'maxTypes',
    '--max-member-lines': 'maxMemberLines',
  };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--help' || arg === '-h') {
      usage();
      process.exit(0);
    }
    if (arg === '--grouped') {
      args.grouped = true;
    } else if (arg === '--split') {
      args.split = true;
    } else if (arg === '--project') {
      const value = argv[++i];
      if (!value) throw new Error('Missing value for --project');
      args.project = value;
    } else if (numeric.has(arg)) {
      const value = Number(argv[++i]);
      if (!Number.isInteger(value) || value < 1) throw new Error(`Invalid value for ${arg}`);
      args[byFlag[arg]] = value;
    } else if (!args.file) {
      args.file = arg;
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }
  if (!args.file) throw new Error('Missing diagram file');
  return args;
}

function findNodeModules(startDir) {
  const candidates = [];
  if (process.env.TECHNE_VIZ_NODE_MODULES) {
    candidates.push(process.env.TECHNE_VIZ_NODE_MODULES);
  }
  candidates.push(path.join(path.dirname(new URL(import.meta.url).pathname), 'node_modules'));
  let dir = startDir;
  while (true) {
    candidates.push(path.join(dir, 'node_modules'));
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  for (const candidate of candidates) {
    if (candidate && fs.existsSync(path.join(candidate, 'mermaid')) && fs.existsSync(path.join(candidate, 'jsdom'))) {
      return candidate;
    }
  }
  throw new Error('Missing dependencies: install mermaid@11.15.0 and jsdom, or set TECHNE_VIZ_NODE_MODULES=/path/to/node_modules');
}

async function loadMermaid(nodeModules) {
  const require = createRequire(import.meta.url);
  const jsdomPath = require.resolve('jsdom', { paths: [nodeModules] });
  const mermaidPath = require.resolve('mermaid', { paths: [nodeModules] });
  const { JSDOM } = await import(pathToFileURL(jsdomPath).href);
  const { window } = new JSDOM('<!doctype html><html><body></body></html>');
  globalThis.window = window;
  globalThis.document = window.document;
  globalThis.Element = window.Element;
  globalThis.HTMLElement = window.HTMLElement;
  globalThis.SVGElement = window.SVGElement;
  Object.defineProperty(globalThis, 'navigator', { value: window.navigator, configurable: true });
  const mod = await import(pathToFileURL(mermaidPath).href);
  const mermaid = mod.default || mod;
  mermaid.initialize({ startOnLoad: false, securityLevel: 'strict' });
  return mermaid;
}

function extractMermaid(text) {
  const fence = text.match(/```(?:mermaid|mmd)\s*\n([\s\S]*?)```/i);
  return (fence ? fence[1] : text).trim();
}

function contentLines(source) {
  return source.split(/\r?\n/).map((raw, index) => ({ raw, line: raw.trim(), index }));
}

function isIgnorable(line) {
  return !line || line.startsWith('%%');
}

function detectType(source) {
  const first = contentLines(source).find(({ line }) => !isIgnorable(line));
  if (!first) throw new Error('Diagram is empty');
  const match = first.line.match(/^([A-Za-z][\w-]*)\b/);
  if (!match) throw new Error(`Unsupported Mermaid type: ${first.line}`);
  const key = match[1].toLowerCase();
  if (!TYPE_TO_KIND[key]) {
    throw new Error(`Unsupported Mermaid type: ${match[1]}; supported: flowchart, graph, sequenceDiagram, erDiagram, stateDiagram-v2, stateDiagram, classDiagram`);
  }
  return {
    headerIndex: first.index,
    diagramKind: TYPE_TO_KIND[key],
    mermaidType: CANONICAL_TYPES[key],
  };
}

function bodyLines(source, headerIndex) {
  return contentLines(source).filter(({ index, line }) => index > headerIndex && !isIgnorable(line));
}

function stripStrings(line) {
  return line
    .replace(/"[^"]*"/g, '""')
    .replace(/'[^']*'/g, "''")
    .replace(/`[^`]*`/g, '``');
}

function stripNodeText(line) {
  return line
    .replace(/\[[^\]]*\]/g, '')
    .replace(/\([^)]*\)/g, '')
    .replace(/\{[^}]*\}/g, '')
    .replace(/\|[^|]*\|/g, '');
}

function normalizeEdges(line) {
  return line
    .replace(/-\.[^.]*\.->/g, '-->')
    .replace(/--[^-<>]*-->/g, '-->')
    .replace(/==[^=<>]*==>/g, '==>');
}

function failClosed(line, reason) {
  throw new Error(`syntax is renderable but not countable by techne: ${reason}: ${line}; simplify, split, or narrow scope`);
}

function assertLimit(value, max, label, action = 'split, simplify, or narrow scope') {
  if (value > max) {
    throw new Error(`${label} count ${value} exceeds max ${max}; ${action}`);
  }
}

function uniqueSorted(values) {
  return [...new Set(values)].sort((a, b) => a.localeCompare(b));
}

function elementMap(elements) {
  return new Map(elements.map((element) => [element.ref, element]));
}

function relationshipRef(from, to) {
  return `${from}->${to}`;
}

function addEntity(entities, id, attrs = {}) {
  if (id === '[*]') return;
  const existing = entities.get(id);
  if (!existing) {
    entities.set(id, { ref: id, kind: 'entity', ...attrs });
    return;
  }
  const merged = { ...existing, ...attrs };
  if (existing.actor || attrs.actor) merged.actor = true;
  if (existing.participantKind === 'actor' || attrs.participantKind === 'actor') {
    merged.participantKind = 'actor';
  }
  entities.set(id, merged);
}

function addRelationship(relationships, from, to, attrs = {}) {
  relationships.set(relationshipRef(from, to), {
    ref: relationshipRef(from, to),
    kind: 'relationship',
    endpoints: [from, to],
    ...attrs,
  });
}

function tokenIds(fragment) {
  const matches = fragment.match(ID_SCAN_RE) || [];
  return matches.filter((id) => !['classDef', 'class', 'style', 'linkStyle', 'click'].includes(id));
}

function singleId(fragment, line) {
  const ids = tokenIds(fragment);
  if (ids.length !== 1) failClosed(line, 'unsupported architecture multi-node fragment');
  return ids[0];
}

function analyzeArchitecture(source, headerIndex, args, text) {
  const entities = new Map();
  const relationships = new Map();
  const topLevelNodes = new Set();
  let depth = 0;
  const edgeSplitRe = /\s*(?:<-->|-->|---|==>|~~~|o--|--o|x--|--x)\s*/;

  for (const { line } of contentLines(source)) {
    if (!line || line.startsWith('%%') || /^(flowchart|graph)\b/i.test(line)) continue;
    if (/^subgraph\b/i.test(line)) {
      depth += 1;
      continue;
    }
    if (/^end\b/i.test(line)) {
      depth = Math.max(0, depth - 1);
      continue;
    }
    if (/^direction\s+(TB|BT|RL|LR)$/i.test(line)) continue;
    if (/^(classDef|class|style|linkStyle|click)\b/i.test(line)) continue;

    const normalized = normalizeEdges(stripNodeText(stripStrings(line)));
    if (edgeSplitRe.test(normalized)) {
      const fragments = normalized.split(edgeSplitRe).filter((fragment) => fragment.trim());
      if (fragments.length < 2) failClosed(line, 'unsupported architecture edge syntax');
      const ids = fragments.map((fragment) => singleId(fragment, line));
      for (const id of ids) {
        addEntity(entities, id, { diagramKind: 'architecture' });
        if (depth === 0) topLevelNodes.add(id);
      }
      for (let i = 0; i < ids.length - 1; i += 1) {
        addRelationship(relationships, ids[i], ids[i + 1], { diagramKind: 'architecture' });
      }
      continue;
    }

    const ids = tokenIds(normalized);
    if (ids.length === 1) {
      addEntity(entities, ids[0], { diagramKind: 'architecture' });
      if (depth === 0) topLevelNodes.add(ids[0]);
      continue;
    }
    failClosed(line, 'unsupported architecture syntax');
  }

  const groupedOrSplit = args.grouped || args.split || /techne-viz:\s*(grouped|split)\s*=\s*true/i.test(text);
  if (topLevelNodes.size > args.maxNodes && !groupedOrSplit) {
    throw new Error(`Top-level node count ${topLevelNodes.size} exceeds max ${args.maxNodes}; group into subgraphs or mark grouped/split`);
  }
  return {
    counts: { topLevelNodes: topLevelNodes.size },
    limits: { maxNodes: args.maxNodes },
    groupedOrSplit,
    elements: [...entities.values(), ...relationships.values()],
  };
}

function analyzeSequence(source, headerIndex, args) {
  const entities = new Map();
  const relationships = new Map();
  let messages = 0;
  for (const { line } of bodyLines(source, headerIndex)) {
    if (/^(loop|alt|else|opt|par|and|critical|option|break|box|end|rect|create|destroy|activate|deactivate)\b/i.test(line)) {
      failClosed(line, 'unsupported sequence control or lifecycle syntax');
    }
    if (/^(autonumber|title|accTitle|accDescr)\b/i.test(line)) continue;
    const declaration = line.match(/^(participant|actor)\s+([A-Za-z_][\w.]*)((?:\s+as\s+.+)?)$/i);
    if (declaration) {
      addEntity(entities, declaration[2], {
        diagramKind: 'interaction',
        participantKind: declaration[1].toLowerCase(),
        actor: declaration[1].toLowerCase() === 'actor',
      });
      continue;
    }
    const note = line.match(/^Note\s+(?:over|right of|left of)\s+(.+?)\s*:/i);
    if (note) {
      for (const id of note[1].split(',').map((item) => item.trim()).filter(Boolean)) {
        if (!/^[A-Za-z_][\w.]*$/.test(id)) failClosed(line, 'unsupported sequence note participant syntax');
        addEntity(entities, id, { diagramKind: 'interaction', participantKind: 'implicit', actor: false });
      }
      continue;
    }
    const message = line.match(/^([A-Za-z_][\w.]*)\s*-{1,2}(?:>>|>|x|\))\s*([A-Za-z_][\w.]*)\s*:/);
    if (message) {
      addEntity(entities, message[1], { diagramKind: 'interaction', participantKind: 'implicit', actor: false });
      addEntity(entities, message[2], { diagramKind: 'interaction', participantKind: 'implicit', actor: false });
      addRelationship(relationships, message[1], message[2], { diagramKind: 'interaction' });
      messages += 1;
      continue;
    }
    failClosed(line, 'unsupported sequence syntax');
  }
  assertLimit(entities.size, args.maxParticipants, 'Participant');
  assertLimit(messages, args.maxMessages, 'Message');
  return {
    counts: { participants: entities.size, messages },
    limits: { maxParticipants: args.maxParticipants, maxMessages: args.maxMessages },
    groupedOrSplit: false,
    elements: [...entities.values(), ...relationships.values()],
  };
}

function analyzeEr(source, headerIndex, args) {
  const entities = new Map();
  const relationships = new Map();
  let relationshipLines = 0;
  let inEntity = null;
  for (const { line } of bodyLines(source, headerIndex)) {
    if (inEntity) {
      if (line === '}') {
        inEntity = null;
        continue;
      }
      if (/[{}]/.test(line)) failClosed(line, 'unsupported ER entity block syntax');
      continue;
    }
    const block = line.match(/^([A-Za-z_][\w-]*)\s*\{$/);
    if (block) {
      addEntity(entities, block[1], { diagramKind: 'data-model' });
      inEntity = block[1];
      continue;
    }
    if (line === '}') failClosed(line, 'unmatched ER entity block close');
    const relationship = line.match(/^([A-Za-z_][\w-]*)\s+[|}{o]+\s*(?:--|\.\.)\s*[|}{o]+\s+([A-Za-z_][\w-]*)\s*:/);
    if (relationship) {
      addEntity(entities, relationship[1], { diagramKind: 'data-model' });
      addEntity(entities, relationship[2], { diagramKind: 'data-model' });
      addRelationship(relationships, relationship[1], relationship[2], { diagramKind: 'data-model' });
      relationshipLines += 1;
      continue;
    }
    failClosed(line, 'unsupported ER syntax');
  }
  if (inEntity) failClosed(inEntity, 'unclosed ER entity block');
  assertLimit(entities.size, args.maxEntities, 'Entity');
  assertLimit(relationshipLines, args.maxRelationships, 'Relationship');
  return {
    counts: { entities: entities.size, relationships: relationshipLines },
    limits: { maxEntities: args.maxEntities, maxRelationships: args.maxRelationships },
    groupedOrSplit: false,
    elements: [...entities.values(), ...relationships.values()],
  };
}

function analyzeState(source, headerIndex, args) {
  const entities = new Map();
  const relationships = new Map();
  let transitions = 0;
  for (const { line } of bodyLines(source, headerIndex)) {
    if (/^direction\s+(TB|BT|RL|LR)$/i.test(line)) continue;
    if (/^state\s+["']/i.test(line) || /<<[^>]+>>/.test(line) || line === '--' || /[{}]/.test(line)) {
      failClosed(line, 'unsupported nested/composite/fork state syntax');
    }
    const stateDecl = line.match(/^state\s+([A-Za-z_][\w.-]*)$/i);
    if (stateDecl) {
      addEntity(entities, stateDecl[1], { diagramKind: 'state-model' });
      continue;
    }
    const transition = line.match(/^(\[\*\]|[A-Za-z_][\w.-]*)\s*-->\s*(\[\*\]|[A-Za-z_][\w.-]*)(?:\s*:\s*.+)?$/);
    if (transition) {
      addEntity(entities, transition[1], { diagramKind: 'state-model' });
      addEntity(entities, transition[2], { diagramKind: 'state-model' });
      addRelationship(relationships, transition[1], transition[2], { diagramKind: 'state-model' });
      transitions += 1;
      continue;
    }
    const simpleState = line.match(/^([A-Za-z_][\w.-]*)(?:\s*:\s*.+)?$/);
    if (simpleState) {
      addEntity(entities, simpleState[1], { diagramKind: 'state-model' });
      continue;
    }
    failClosed(line, 'unsupported state syntax');
  }
  assertLimit(entities.size, args.maxStates, 'State');
  assertLimit(transitions, args.maxTransitions, 'Transition');
  return {
    counts: { states: entities.size, transitions },
    limits: { maxStates: args.maxStates, maxTransitions: args.maxTransitions },
    groupedOrSplit: false,
    elements: [...entities.values(), ...relationships.values()],
  };
}

function analyzeClass(source, headerIndex, args) {
  const entities = new Map();
  const relationships = new Map();
  let relationshipLines = 0;
  let memberLines = 0;
  let inClass = null;
  for (const { line } of bodyLines(source, headerIndex)) {
    if (/^namespace\b/i.test(line) || /<<[^>]+>>/.test(line) || /~/.test(line)) {
      failClosed(line, 'unsupported class namespace, annotation, or generic syntax');
    }
    if (inClass) {
      if (line === '}') {
        inClass = null;
        continue;
      }
      if (/[{}]/.test(line)) failClosed(line, 'unsupported class block syntax');
      memberLines += 1;
      continue;
    }
    const block = line.match(/^class\s+([A-Za-z_][\w.-]*)\s*\{$/i);
    if (block) {
      addEntity(entities, block[1], { diagramKind: 'type-structure' });
      inClass = block[1];
      continue;
    }
    const declaration = line.match(/^class\s+([A-Za-z_][\w.-]*)$/i);
    if (declaration) {
      addEntity(entities, declaration[1], { diagramKind: 'type-structure' });
      continue;
    }
    if (line === '}') failClosed(line, 'unmatched class block close');
    const relationship = line.match(/^([A-Za-z_][\w.-]*)\s+(<\|--|<\|\.\.|\*--|o--|-->|--|\.\.>|\.\.\|>|\.\.)\s+([A-Za-z_][\w.-]*)(?:\s*:.*)?$/);
    if (relationship) {
      addEntity(entities, relationship[1], { diagramKind: 'type-structure' });
      addEntity(entities, relationship[3], { diagramKind: 'type-structure' });
      addRelationship(relationships, relationship[1], relationship[3], { diagramKind: 'type-structure' });
      relationshipLines += 1;
      continue;
    }
    const member = line.match(/^([A-Za-z_][\w.-]*)\s*:\s*.+$/);
    if (member) {
      addEntity(entities, member[1], { diagramKind: 'type-structure' });
      memberLines += 1;
      continue;
    }
    failClosed(line, 'unsupported class syntax');
  }
  if (inClass) failClosed(inClass, 'unclosed class block');
  const relationshipOrMemberLines = relationshipLines + memberLines;
  assertLimit(entities.size, args.maxTypes, 'Type');
  assertLimit(relationshipOrMemberLines, args.maxMemberLines, 'Relationship/member line');
  return {
    counts: { types: entities.size, relationshipLines, memberLines, relationshipOrMemberLines },
    limits: { maxTypes: args.maxTypes, maxMemberLines: args.maxMemberLines },
    groupedOrSplit: false,
    elements: [...entities.values(), ...relationships.values()],
  };
}

function analyzeDiagram(source, detected, args, text) {
  if (detected.diagramKind === 'architecture') return analyzeArchitecture(source, detected.headerIndex, args, text);
  if (detected.diagramKind === 'interaction') return analyzeSequence(source, detected.headerIndex, args);
  if (detected.diagramKind === 'data-model') return analyzeEr(source, detected.headerIndex, args);
  if (detected.diagramKind === 'state-model') return analyzeState(source, detected.headerIndex, args);
  if (detected.diagramKind === 'type-structure') return analyzeClass(source, detected.headerIndex, args);
  throw new Error(`Unsupported diagram kind: ${detected.diagramKind}`);
}

function parseCitation(token, lineNumber) {
  const hash = token.indexOf('#');
  const rawPath = hash === -1 ? token : token.slice(0, hash);
  const symbol = hash === -1 ? null : token.slice(hash + 1);
  if (!rawPath) throw new Error(`Invalid techne:source path on line ${lineNumber}`);
  if (symbol !== null && !symbol) throw new Error(`Invalid empty techne:source symbol on line ${lineNumber}`);
  if (symbol !== null && !/^[^\s]+$/.test(symbol)) throw new Error(`Invalid techne:source symbol on line ${lineNumber}; symbols must be printable non-whitespace`);
  return { rawPath, symbol };
}

function parseAnnotations(source) {
  const annotations = { sources: [], inferred: [] };
  for (const { raw, line, index } of contentLines(source)) {
    if (!line.startsWith('%%')) continue;
    const techne = line.match(/^%%\s*techne:(\S+)\s*(.*)$/);
    if (!techne) continue;
    const directive = techne[1];
    const rest = techne[2].trim();
    if (directive === 'source') {
      const parts = rest.split(/\s+/).filter(Boolean);
      if (parts.length !== 2) throw new Error(`Malformed techne:source on line ${index + 1}; expected: %% techne:source <elementRef> <path>[#symbol]`);
      annotations.sources.push({
        directive,
        line: index + 1,
        raw,
        ref: parts[0],
        citation: parseCitation(parts[1], index + 1),
      });
      continue;
    }
    if (directive === 'inferred') {
      const match = rest.match(/^(\S+)\s+(.+)$/);
      if (!match) throw new Error(`Malformed techne:inferred on line ${index + 1}; expected: %% techne:inferred <relationshipRef> <reason>`);
      annotations.inferred.push({
        directive,
        line: index + 1,
        raw,
        ref: match[1],
        reason: match[2].trim(),
      });
      continue;
    }
    throw new Error(`Unknown reserved techne directive on line ${index + 1}: techne:${directive}`);
  }
  return annotations;
}

function normalizeProjectPath(rawPath) {
  if (path.posix.isAbsolute(rawPath) || rawPath.includes('\\')) {
    return { error: 'path must be POSIX-style relative to the project root' };
  }
  const normalized = path.posix.normalize(rawPath);
  if (!normalized || normalized === '..' || normalized.startsWith('../')) {
    return { error: 'path escapes the project root' };
  }
  return { normalized };
}

function resolveInsideRoot(projectRoot, normalized) {
  const target = path.resolve(projectRoot, ...normalized.split('/'));
  const relative = path.relative(projectRoot, target);
  if (relative.startsWith('..') || path.isAbsolute(relative)) {
    return { error: 'path escapes the project root' };
  }
  return { target };
}

function realpathInsideRoot(projectRoot, target) {
  const realTarget = fs.realpathSync(target);
  const relative = path.relative(projectRoot, realTarget);
  if (relative.startsWith('..') || path.isAbsolute(relative)) {
    return { error: 'source path resolves outside the project root' };
  }
  return { realTarget };
}

function addFailure(failures, ref, kind, message, extra = {}) {
  failures.push({ ref, kind, message, ...extra });
}

function isWordChar(value) {
  return WORD_CHAR_RE.test(value);
}

function containsSymbol(text, symbol) {
  let start = text.indexOf(symbol);
  while (start !== -1) {
    const end = start + symbol.length;
    const first = symbol[0];
    const last = symbol[symbol.length - 1];
    const leftOk = !isWordChar(first) || start === 0 || !isWordChar(text[start - 1]);
    const rightOk = !isWordChar(last) || end >= text.length || !isWordChar(text[end]);
    if (leftOk && rightOk) return true;
    start = text.indexOf(symbol, start + 1);
  }
  return false;
}

function isArchitectureNode(element) {
  return element.kind === 'entity' && element.diagramKind === 'architecture';
}

function isActorParticipant(element) {
  return element.kind === 'entity' && element.diagramKind === 'interaction' && element.actor === true;
}

function verifySourceAnnotation(annotation, element, projectRoot, failures) {
  const { rawPath, symbol } = annotation.citation;
  const normalizedResult = normalizeProjectPath(rawPath);
  if (normalizedResult.error) {
    addFailure(failures, annotation.ref, 'invalid_path', normalizedResult.error, { line: annotation.line, path: rawPath });
    return null;
  }
  const normalizedPath = normalizedResult.normalized;
  const resolved = resolveInsideRoot(projectRoot, normalizedPath);
  if (resolved.error) {
    addFailure(failures, annotation.ref, 'invalid_path', resolved.error, { line: annotation.line, path: rawPath });
    return null;
  }
  if (!fs.existsSync(resolved.target)) {
    addFailure(failures, annotation.ref, 'missing_path', 'source path does not exist', { line: annotation.line, path: normalizedPath });
    return null;
  }
  const realResolved = realpathInsideRoot(projectRoot, resolved.target);
  if (realResolved.error) {
    addFailure(failures, annotation.ref, 'invalid_path', realResolved.error, { line: annotation.line, path: normalizedPath });
    return null;
  }
  const stats = fs.statSync(resolved.target);
  if (stats.isDirectory()) {
    if (symbol) {
      addFailure(failures, annotation.ref, 'citation_strength', 'directory citations cannot include #symbol', { line: annotation.line, path: normalizedPath });
      return null;
    }
    if (!isArchitectureNode(element)) {
      addFailure(failures, annotation.ref, 'citation_strength', 'directory citations are valid only for architecture nodes', { line: annotation.line, path: normalizedPath });
      return null;
    }
    return { strength: 'pathVerified', path: normalizedPath };
  }
  if (!stats.isFile()) {
    addFailure(failures, annotation.ref, 'invalid_path', 'source path must be a file or directory', { line: annotation.line, path: normalizedPath });
    return null;
  }
  if (!symbol) {
    if (isArchitectureNode(element) || isActorParticipant(element)) {
      return { strength: 'pathVerified', path: normalizedPath };
    }
    addFailure(failures, annotation.ref, 'citation_strength', 'file path-only citations are valid only for architecture nodes and actor participants', { line: annotation.line, path: normalizedPath });
    return null;
  }
  const text = fs.readFileSync(realResolved.realTarget, 'utf8');
  if (!containsSymbol(text, symbol)) {
    addFailure(failures, annotation.ref, 'symbol_not_found', 'symbol was not found in source file', { line: annotation.line, path: normalizedPath, symbol });
    return null;
  }
  return { strength: 'symbolVerified', path: normalizedPath, symbol };
}

function bestStrength(records) {
  if (records.some((record) => record.strength === 'symbolVerified')) return 'symbolVerified';
  if (records.some((record) => record.strength === 'pathVerified')) return 'pathVerified';
  return null;
}

function validateProvenance({ annotations, elements, projectRoot }) {
  const map = elementMap(elements);
  const failures = [];
  const sourceRecords = new Map(elements.map((element) => [element.ref, []]));
  const inferredRefs = new Set();

  for (const annotation of annotations.sources) {
    const element = map.get(annotation.ref);
    if (!element) {
      addFailure(failures, annotation.ref, 'unknown_ref', 'annotation references an element not present in the diagram', { line: annotation.line });
      continue;
    }
    if (element.kind === 'relationship' && !annotation.citation.symbol) {
      addFailure(failures, annotation.ref, 'citation_strength', 'relationship-like source annotations require #symbol', { line: annotation.line, path: annotation.citation.rawPath });
      continue;
    }
    const verified = verifySourceAnnotation(annotation, element, projectRoot, failures);
    if (verified) sourceRecords.get(annotation.ref).push(verified);
  }

  const entityStatus = new Map();
  for (const element of elements.filter((item) => item.kind === 'entity')) {
    const strength = bestStrength(sourceRecords.get(element.ref) || []);
    if (strength) {
      entityStatus.set(element.ref, strength);
    } else {
      entityStatus.set(element.ref, 'uncovered');
      addFailure(failures, element.ref, 'uncovered', 'entity-like element requires a verified techne:source');
    }
  }

  for (const annotation of annotations.inferred) {
    const element = map.get(annotation.ref);
    if (!element) {
      addFailure(failures, annotation.ref, 'unknown_ref', 'annotation references an element not present in the diagram', { line: annotation.line });
      continue;
    }
    if (element.kind !== 'relationship') {
      addFailure(failures, annotation.ref, 'invalid_inferred', 'techne:inferred is valid only for relationship-like elements', { line: annotation.line });
      continue;
    }
    const missingEndpoint = element.endpoints.find((endpoint) => endpoint !== '[*]' && entityStatus.get(endpoint) === 'uncovered');
    if (missingEndpoint) {
      addFailure(failures, annotation.ref, 'invalid_inferred', `inferred relationship endpoint is not sourced: ${missingEndpoint}`, { line: annotation.line });
      continue;
    }
    inferredRefs.add(annotation.ref);
  }

  const elementStatuses = new Map();
  for (const element of elements) {
    const sourceStrength = bestStrength(sourceRecords.get(element.ref) || []);
    if (element.kind === 'entity') {
      elementStatuses.set(element.ref, sourceStrength || 'uncovered');
      continue;
    }
    if (sourceStrength === 'symbolVerified') {
      elementStatuses.set(element.ref, 'symbolVerified');
    } else if (inferredRefs.has(element.ref)) {
      elementStatuses.set(element.ref, 'inferred');
    } else {
      elementStatuses.set(element.ref, 'uncovered');
      addFailure(failures, element.ref, 'uncovered', 'relationship-like element requires a symbol-verified techne:source or valid techne:inferred');
    }
  }

  const coverage = {
    elements: elements.length,
    symbolVerified: 0,
    pathVerified: 0,
    inferred: 0,
    uncovered: 0,
    ratio: 0,
  };
  for (const status of elementStatuses.values()) {
    if (status === 'symbolVerified') coverage.symbolVerified += 1;
    else if (status === 'pathVerified') coverage.pathVerified += 1;
    else if (status === 'inferred') coverage.inferred += 1;
    else coverage.uncovered += 1;
  }
  coverage.ratio = coverage.elements ? Number((coverage.symbolVerified / coverage.elements).toFixed(2)) : 0;

  const sourceFiles = uniqueSorted([...sourceRecords.values()].flat().map((record) => record.path));
  return {
    ok: failures.length === 0,
    coverage,
    sourceFiles,
    provenance: {
      verified: failures.length === 0,
      failures,
      annotations: {
        sources: annotations.sources.length,
        inferred: annotations.inferred.length,
      },
    },
  };
}

function unverifiedProvenance(annotations) {
  return {
    provenance: {
      verified: false,
      failures: [],
      annotations: {
        sources: annotations.sources.length,
        inferred: annotations.inferred.length,
      },
    },
  };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const text = fs.readFileSync(args.file, 'utf8');
  const source = extractMermaid(text);
  const detected = detectType(source);
  const annotations = parseAnnotations(source);
  const mermaid = await loadMermaid(findNodeModules(process.cwd()));
  await mermaid.parse(source, { suppressErrors: false });
  const measured = analyzeDiagram(source, detected, args, text);
  const output = {
    ok: true,
    diagramKind: detected.diagramKind,
    mermaidType: detected.mermaidType,
    diagramType: detected.mermaidType,
    counts: measured.counts,
    limits: measured.limits,
    groupedOrSplit: measured.groupedOrSplit,
  };
  Object.assign(output, measured.counts);

  if (args.project) {
    const projectPath = path.resolve(args.project);
    if (!fs.existsSync(projectPath) || !fs.statSync(projectPath).isDirectory()) {
      throw new Error(`Project directory does not exist: ${projectPath}`);
    }
    const projectRoot = fs.realpathSync(projectPath);
    const provenance = validateProvenance({ annotations, elements: measured.elements, projectRoot });
    Object.assign(output, {
      provenance: provenance.provenance,
      coverage: provenance.coverage,
      sourceFiles: provenance.sourceFiles,
    });
    if (!provenance.ok) {
      output.ok = false;
      throw new ProvenanceError(output);
    }
  } else {
    Object.assign(output, unverifiedProvenance(annotations));
  }

  console.log(JSON.stringify(output));
}

main().catch((error) => {
  if (error instanceof ProvenanceError) {
    console.error(JSON.stringify(error.payload));
  } else {
    console.error(error.message || String(error));
  }
  process.exit(1);
});
