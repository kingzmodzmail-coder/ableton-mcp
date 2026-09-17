import os
root = r'C:\Users\Gebruiker\ableton-mcp\music-os-bridge'
server = '''#!/usr/bin/env node
/**
 * Music OS bridge on PC — MDBP v0 + live AbletonMCP TCP (:9877)
 */
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { WebSocketServer } from 'ws';
import { abletonEndpoint, fetchSessionSummary } from './ableton.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WATCH_DIR = process.env.MUSIC_OS_WATCH_DIR
  ? path.resolve(process.env.MUSIC_OS_WATCH_DIR)
  : path.join(__dirname, 'export-watch');
const HOST = process.env.MUSIC_OS_BRIDGE_HOST || '127.0.0.1';
const PORT = Number(process.env.MUSIC_OS_BRIDGE_PORT || 7843);

if (!fs.existsSync(WATCH_DIR)) fs.mkdirSync(WATCH_DIR, { recursive: true });

const recentEvents = [];

function uid() {
  return crypto.randomUUID();
}

function envelope(partial) {
  return {
    v: 0,
    id: partial.id ?? uid(),
    dir: partial.dir,
    method: partial.method,
    params: partial.params ?? null,
    error: partial.error ?? null,
    result: partial.result ?? null,
  };
}

async function handleHello(msg, ws) {
  const summary = await fetchSessionSummary();
  ws.send(
    JSON.stringify(
      envelope({
        id: msg.id,
        dir: 'res',
        method: 'hello.ok',
        result: {
          protocol: 'MDBP',
          version: 0,
          caps: ['export_watch', 'summary', 'ableton_tcp'],
          daw: 'ableton',
          dawOnline: !!summary.dawOnline,
          watching: WATCH_DIR,
          bridge: 'music-os-pc-ableton-bridge',
          ableton: abletonEndpoint(),
        },
      }),
    ),
  );
}

async function handleSummary(msg, ws) {
  const summary = await fetchSessionSummary();
  ws.send(
    JSON.stringify(
      envelope({
        id: msg.id,
        dir: 'res',
        method: 'session.summary',
        result: summary,
      }),
    ),
  );
}

async function onMessage(ws, raw) {
  let msg;
  try {
    msg = JSON.parse(String(raw));
  } catch {
    ws.send(
      JSON.stringify(
        envelope({
          dir: 'res',
          method: 'error',
          error: { code: 'bad_json', message: 'Invalid JSON' },
        }),
      ),
    );
    return;
  }
  const method = msg.method || msg.type;
  switch (method) {
    case 'hello':
    case 'bridge.hello':
      await handleHello(msg, ws);
      break;
    case 'session.summary.get':
      await handleSummary(msg, ws);
      break;
    case 'ping':
      ws.send(
        JSON.stringify(
          envelope({ id: msg.id, dir: 'res', method: 'pong', result: { ok: true } }),
        ),
      );
      break;
    default:
      ws.send(
        JSON.stringify(
          envelope({
            id: msg.id,
            dir: 'res',
            method: method || 'unknown',
            error: { code: 'unknown_method', message: 'Unknown method: ' + method },
          }),
        ),
      );
  }
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url || '/', 'http://' + HOST + ':' + PORT);
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }
  if (url.pathname === '/health') {
    void (async () => {
      const summary = await fetchSessionSummary();
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(
        JSON.stringify({
          ok: true,
          watching: WATCH_DIR,
          dawOnline: !!summary.dawOnline,
          tempo: summary.tempo,
          tracks: summary.tracks || [],
          ableton: abletonEndpoint(),
          recent: recentEvents.slice(0, 5),
        }),
      );
    })();
    return;
  }
  if (url.pathname === '/session' && req.method === 'GET') {
    void (async () => {
      const summary = await fetchSessionSummary();
      res.writeHead(summary.dawOnline ? 200 : 503, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(summary));
    })();
    return;
  }
  res.writeHead(404, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ ok: false, error: 'not found' }));
});

const wss = new WebSocketServer({ server });
wss.on('connection', (ws) => {
  console.log('[bridge] client connected');
  ws.on('message', (data) => {
    void onMessage(ws, data);
  });
  ws.on('close', () => console.log('[bridge] client disconnected'));
  void handleHello({ id: uid() }, ws);
});

server.listen(PORT, HOST, () => {
  console.log('[bridge] MDBP + Ableton on http://' + HOST + ':' + PORT);
  console.log('[bridge] Ableton TCP ' + JSON.stringify(abletonEndpoint()));
  console.log('[bridge] watching ' + WATCH_DIR);
});

process.on('SIGINT', () => {
  server.close();
  process.exit(0);
});
'''
open(os.path.join(root, 'server.mjs'), 'w', encoding='utf-8', newline='\n').write(server)
print('server ok', len(server))
