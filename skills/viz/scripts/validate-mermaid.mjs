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

function usage() {
  console.error(`Usage: validate-mermaid.mjs <diagram.md|diagram.mmd> [options]

Options:
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
  const args = { ...LIMITS, grouped: false, split: false, file: null };
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

function collectIds(fragment, ids) {
  const ignored = new Set(['classDef', 'class', 'style', 'linkStyle', 'click']);
  const matches = fragment.match(/[A-Za-z_][\w:-]*/g) || [];
  for (const id of matches) {
    if (!ignored.has(id)) ids.add(id);
  }
}

function countTopLevelNodes(source) {
  const nodes = new Set();
  let depth = 0;
  const lines = source.split(/\r?\n/);
  for (const raw of lines) {
    const trimmed = raw.trim();
    if (!trimmed || trimmed.startsWith('%%')) continue;
    if (/^subgraph\b/i.test(trimmed)) {
      depth += 1;
      continue;
    }
    if (/^end\b/i.test(trimmed)) {
      depth = Math.max(0, depth - 1);
      continue;
    }
    if (/^(flowchart|graph)\b/i.test(trimmed) || depth > 0) continue;
    const line = normalizeEdges(stripNodeText(stripStrings(trimmed)));
    if (/^(classDef|class|style|linkStyle|click)\b/.test(line)) continue;
    if (/(-->|---|==>|~~~|<-->|o--|--o|x--|--x)/.test(line)) {
      const fragments = line.split(/\s*(?:-->|---|==>|~~~|<-->|o--|--o|x--|--x)\s*/);
      for (const fragment of fragments) collectIds(fragment, nodes);
    } else {
      const match = line.trim().match(/^([A-Za-z_][\w:-]*)/);
      if (match) nodes.add(match[1]);
    }
  }
  return nodes.size;
}

function failClosed(line, reason) {
  throw new Error(`syntax is renderable but not countable by techne: ${reason}: ${line}; simplify, split, or narrow scope`);
}

function assertLimit(value, max, label, action = 'split, simplify, or narrow scope') {
  if (value > max) {
    throw new Error(`${label} count ${value} exceeds max ${max}; ${action}`);
  }
}

function countSequence(source, headerIndex, args) {
  const participants = new Set();
  let messages = 0;
  for (const { line } of bodyLines(source, headerIndex)) {
    if (/^(loop|alt|else|opt|par|and|critical|option|break|box|end|rect|create|destroy|activate|deactivate)\b/i.test(line)) {
      failClosed(line, 'unsupported sequence control or lifecycle syntax');
    }
    if (/^(autonumber|title|accTitle|accDescr)\b/i.test(line)) continue;
    const declaration = line.match(/^(participant|actor)\s+([A-Za-z_][\w.]*)(?:\s+as\s+.+)?$/i);
    if (declaration) {
      participants.add(declaration[2]);
      continue;
    }
    const note = line.match(/^Note\s+(?:over|right of|left of)\s+(.+?)\s*:/i);
    if (note) {
      for (const id of note[1].split(',').map((item) => item.trim()).filter(Boolean)) {
        if (!/^[A-Za-z_][\w.]*$/.test(id)) failClosed(line, 'unsupported sequence note participant syntax');
        participants.add(id);
      }
      continue;
    }
    const message = line.match(/^([A-Za-z_][\w.]*)\s*-{1,2}(?:>>|>|x|\))\s*([A-Za-z_][\w.]*)\s*:/);
    if (message) {
      participants.add(message[1]);
      participants.add(message[2]);
      messages += 1;
      continue;
    }
    failClosed(line, 'unsupported sequence syntax');
  }
  assertLimit(participants.size, args.maxParticipants, 'Participant');
  assertLimit(messages, args.maxMessages, 'Message');
  return {
    counts: { participants: participants.size, messages },
    limits: { maxParticipants: args.maxParticipants, maxMessages: args.maxMessages },
  };
}

function countEr(source, headerIndex, args) {
  const entities = new Set();
  let relationships = 0;
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
      entities.add(block[1]);
      inEntity = block[1];
      continue;
    }
    if (line === '}') failClosed(line, 'unmatched ER entity block close');
    const relationship = line.match(/^([A-Za-z_][\w-]*)\s+[|}{o]+\s*(?:--|\.\.)\s*[|}{o]+\s+([A-Za-z_][\w-]*)\s*:/);
    if (relationship) {
      entities.add(relationship[1]);
      entities.add(relationship[2]);
      relationships += 1;
      continue;
    }
    failClosed(line, 'unsupported ER syntax');
  }
  if (inEntity) failClosed(inEntity, 'unclosed ER entity block');
  assertLimit(entities.size, args.maxEntities, 'Entity');
  assertLimit(relationships, args.maxRelationships, 'Relationship');
  return {
    counts: { entities: entities.size, relationships },
    limits: { maxEntities: args.maxEntities, maxRelationships: args.maxRelationships },
  };
}

function addState(states, id) {
  if (id !== '[*]') states.add(id);
}

function countState(source, headerIndex, args) {
  const states = new Set();
  let transitions = 0;
  for (const { line } of bodyLines(source, headerIndex)) {
    if (/^direction\s+(TB|BT|RL|LR)$/i.test(line)) continue;
    if (/^state\s+["']/i.test(line) || /<<[^>]+>>/.test(line) || line === '--' || /[{}]/.test(line)) {
      failClosed(line, 'unsupported nested/composite/fork state syntax');
    }
    const stateDecl = line.match(/^state\s+([A-Za-z_][\w.-]*)$/i);
    if (stateDecl) {
      states.add(stateDecl[1]);
      continue;
    }
    const transition = line.match(/^(\[\*\]|[A-Za-z_][\w.-]*)\s*-->\s*(\[\*\]|[A-Za-z_][\w.-]*)(?:\s*:\s*.+)?$/);
    if (transition) {
      addState(states, transition[1]);
      addState(states, transition[2]);
      transitions += 1;
      continue;
    }
    const simpleState = line.match(/^([A-Za-z_][\w.-]*)(?:\s*:\s*.+)?$/);
    if (simpleState) {
      states.add(simpleState[1]);
      continue;
    }
    failClosed(line, 'unsupported state syntax');
  }
  assertLimit(states.size, args.maxStates, 'State');
  assertLimit(transitions, args.maxTransitions, 'Transition');
  return {
    counts: { states: states.size, transitions },
    limits: { maxStates: args.maxStates, maxTransitions: args.maxTransitions },
  };
}

function countClass(source, headerIndex, args) {
  const types = new Set();
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
      types.add(block[1]);
      inClass = block[1];
      continue;
    }
    const declaration = line.match(/^class\s+([A-Za-z_][\w.-]*)$/i);
    if (declaration) {
      types.add(declaration[1]);
      continue;
    }
    if (line === '}') failClosed(line, 'unmatched class block close');
    const relationship = line.match(/^([A-Za-z_][\w.-]*)\s+(<\|--|<\|\.\.|\*--|o--|-->|--|\.\.>|\.\.\|>|\.\.)\s+([A-Za-z_][\w.-]*)(?:\s*:.*)?$/);
    if (relationship) {
      types.add(relationship[1]);
      types.add(relationship[3]);
      relationshipLines += 1;
      continue;
    }
    const member = line.match(/^([A-Za-z_][\w.-]*)\s*:\s*.+$/);
    if (member) {
      types.add(member[1]);
      memberLines += 1;
      continue;
    }
    failClosed(line, 'unsupported class syntax');
  }
  if (inClass) failClosed(inClass, 'unclosed class block');
  const relationshipOrMemberLines = relationshipLines + memberLines;
  assertLimit(types.size, args.maxTypes, 'Type');
  assertLimit(relationshipOrMemberLines, args.maxMemberLines, 'Relationship/member line');
  return {
    counts: { types: types.size, relationshipLines, memberLines, relationshipOrMemberLines },
    limits: { maxTypes: args.maxTypes, maxMemberLines: args.maxMemberLines },
  };
}

function countDiagram(source, detected, args, text) {
  if (detected.diagramKind === 'architecture') {
    const topLevelNodes = countTopLevelNodes(source);
    const groupedOrSplit = args.grouped || args.split || /techne-viz:\s*(grouped|split)\s*=\s*true/i.test(text);
    if (topLevelNodes > args.maxNodes && !groupedOrSplit) {
      throw new Error(`Top-level node count ${topLevelNodes} exceeds max ${args.maxNodes}; group into subgraphs or mark grouped/split`);
    }
    return {
      counts: { topLevelNodes },
      limits: { maxNodes: args.maxNodes },
      groupedOrSplit,
    };
  }
  if (detected.diagramKind === 'interaction') return { ...countSequence(source, detected.headerIndex, args), groupedOrSplit: false };
  if (detected.diagramKind === 'data-model') return { ...countEr(source, detected.headerIndex, args), groupedOrSplit: false };
  if (detected.diagramKind === 'state-model') return { ...countState(source, detected.headerIndex, args), groupedOrSplit: false };
  if (detected.diagramKind === 'type-structure') return { ...countClass(source, detected.headerIndex, args), groupedOrSplit: false };
  throw new Error(`Unsupported diagram kind: ${detected.diagramKind}`);
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const text = fs.readFileSync(args.file, 'utf8');
  const source = extractMermaid(text);
  const detected = detectType(source);
  const mermaid = await loadMermaid(findNodeModules(process.cwd()));
  await mermaid.parse(source, { suppressErrors: false });
  const measured = countDiagram(source, detected, args, text);
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
  console.log(JSON.stringify(output));
}

main().catch((error) => {
  console.error(error.message || String(error));
  process.exit(1);
});
