/**
 * Ableton Live Remote Script TCP client (AbletonMCP protocol).
 */
import net from 'node:net';

const HOST = process.env.ABLETON_HOST || '127.0.0.1';
const PORT = Number(process.env.ABLETON_PORT || 9877);
const TIMEOUT_MS = Number(process.env.ABLETON_TIMEOUT_MS || 8000);

export function abletonCommand(type, params = {}) {
  return new Promise((resolve) => {
    const socket = new net.Socket();
    const chunks = [];
    let settled = false;
    const done = (value) => {
      if (settled) return;
      settled = true;
      try { socket.destroy(); } catch {}
      resolve(value);
    };
    socket.setTimeout(TIMEOUT_MS);
    socket.once('timeout', () => done({ ok: false, error: 'Ableton timeout ' + HOST + ':' + PORT }));
    socket.once('error', (err) => done({ ok: false, error: err.message || String(err) }));
    socket.on('data', (buf) => {
      chunks.push(buf);
      const raw = Buffer.concat(chunks).toString('utf8');
      try {
        const reply = JSON.parse(raw);
        if (reply.status === 'error') {
          done({ ok: false, error: reply.message || 'Ableton command failed' });
          return;
        }
        done({ ok: true, result: reply.result ?? reply });
      } catch {}
    });
    socket.connect(PORT, HOST, () => {
      socket.write(JSON.stringify({ type, params }));
    });
  });
}

export async function fetchSessionSummary() {
  const session = await abletonCommand('get_session_info');
  if (!session.ok) {
    return {
      online: false,
      dawOnline: false,
      daw: 'ableton',
      reason: session.error,
      host: HOST,
      port: PORT,
    };
  }
  const info = session.result || {};
  const trackCount = Number(info.track_count || 0);
  const tracks = [];
  for (let i = 0; i < trackCount; i++) {
    const tr = await abletonCommand('get_track_info', { track_index: i });
    if (!tr.ok) {
      tracks.push({ index: i, name: 'track_' + i, error: tr.error });
      continue;
    }
    const t = tr.result || {};
    const clips = Array.isArray(t.clip_slots)
      ? t.clip_slots.filter((s) => s && s.has_clip).length
      : 0;
    tracks.push({
      index: t.index ?? i,
      name: t.name || ('track_' + i),
      kind: t.is_midi_track ? 'midi' : t.is_audio_track ? 'audio' : 'unknown',
      mute: !!t.mute,
      solo: !!t.solo,
      arm: !!t.arm,
      clips,
      devices: Array.isArray(t.devices) ? t.devices.length : 0,
    });
  }
  const num = info.signature_numerator || 4;
  const den = info.signature_denominator || 4;
  return {
    online: true,
    dawOnline: true,
    daw: 'ableton',
    tempo: info.tempo,
    timeSignature: String(num) + '/' + String(den),
    isPlaying: !!info.is_playing,
    songTime: info.current_song_time,
    songLength: info.song_length,
    loop: !!info.loop,
    master: info.master_track || null,
    trackCount,
    returnTrackCount: info.return_track_count,
    tracks,
    host: HOST,
    port: PORT,
    source: 'ableton-mcp-tcp',
  };
}

export function abletonEndpoint() {
  return { host: HOST, port: PORT };
}
