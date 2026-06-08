#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';

const MAX_DEFAULT = 15;

function usage() {
  console.error('Usage: validate-mermaid.mjs <diagram.md|diagram.mmd> [--max-nodes 15] [--grouped|--split]');
}

function parseArgs(argv) {
  const args = { maxNodes: MAX_DEFAULT, grouped: false, split: false, file: null };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--max-nodes') {
      args.maxNodes = Number(argv[++i]);
    } else if (arg === '--grouped') {
      args.grouped = true;
    } else if (arg === '--split') {
      args.split = true;
    } else if (!args.file) {
      args.file = arg;
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }
  if (!args.file || !Number.isInteger(args.maxNodes) || args.maxNodes < 1) {
    throw new Error('Missing diagram file or invalid --max-nodes');
  }
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

function assertFlowchart(source) {
  const firstLine = source
    .split(/\r?\n/)
    .map((line) => line.trim())
    .find((line) => line && !line.startsWith('%%'));
  if (!firstLine || !/^(flowchart|graph)\b/i.test(firstLine)) {
    throw new Error('Only Mermaid flowchart/graph diagrams are supported by the viz MVP');
  }
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

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const text = fs.readFileSync(args.file, 'utf8');
  const source = extractMermaid(text);
  assertFlowchart(source);
  const mermaid = await loadMermaid(findNodeModules(process.cwd()));
  await mermaid.parse(source, { suppressErrors: false });
  const topLevelNodes = countTopLevelNodes(source);
  const bypass = args.grouped || args.split || /techne-viz:\s*(grouped|split)\s*=\s*true/i.test(text);
  if (topLevelNodes > args.maxNodes && !bypass) {
    throw new Error(`Top-level node count ${topLevelNodes} exceeds max ${args.maxNodes}; group into subgraphs or mark grouped/split`);
  }
  console.log(JSON.stringify({ ok: true, diagramType: 'flowchart', topLevelNodes, maxNodes: args.maxNodes, groupedOrSplit: bypass }));
}

main().catch((error) => {
  console.error(error.message || String(error));
  process.exit(1);
});
