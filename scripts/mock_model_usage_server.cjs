#!/usr/bin/env node
// Local-only integration fixture: no external models, credentials or billing.
const http = require('node:http');
const events = new Map();
const attempts = [];
const modelCalls = new Map();
const server = http.createServer(async (req, res) => {
  const reply = (code, value) => {
    res.writeHead(code, {'Content-Type': 'application/json'});
    res.end(JSON.stringify(value));
  };
  if (req.method === 'GET' && req.url === '/events') {
    return reply(200, {events: [...events.values()], attempts});
  }
  if (req.method !== 'POST') return reply(404, {error: 'not_found'});
  let raw = '';
  for await (const chunk of req) {
    raw += chunk;
    if (raw.length > 2 * 1024 * 1024) return reply(413, {error: 'too_large'});
  }
  let body;
  try { body = JSON.parse(raw); } catch { return reply(400, {error: 'invalid_json'}); }
  if (req.url.endsWith('/v1/chat/completions')) {
    const planning = /"title"\s*:\s*"Plan"/.test(body.messages?.[0]?.content || "");
    const modelKey = req.url + ':' + planning;
    const previousCalls = modelCalls.get(modelKey) || 0;
    modelCalls.set(modelKey, previousCalls + 1);
    const content = planning
      ? {mode: 'consult', conversation_only: true, use_inventory: false}
      : {message: '这是本地模拟回复，对话正常完成。', looks: [], follow_ups: []};
    return reply(200, {
      id: 'mock-completion', model: 'mock-conversation-model',
      choices: [{message: {content: req.url.includes('json-retry') && planning && previousCalls === 0
        ? 'invalid JSON fixture' : JSON.stringify(content)}}],
      usage: req.url.includes('no-usage') ? undefined : req.url.includes('zero-usage')
        ? {prompt_tokens: 0, completion_tokens: 0}
        : {prompt_tokens: 100, completion_tokens: 20,
          prompt_tokens_details: {cached_tokens: 10}, completion_tokens_details: {reasoning_tokens: 0}}
    });
  }
  if (!['/usage', '/usage-fail', '/usage-bad-ack', '/usage-unauthorized', '/usage-limited', '/usage-timeout'].includes(req.url)) return reply(404, {error: 'not_found'});
  if (req.headers.authorization !== 'Bearer local-user-test') return reply(401, {error: 'unauthorized'});
  attempts.push({event_id: body.event_id, request_id: body.request_id, path: req.url, authenticated_user: '42'});
  if (req.url === '/usage-unauthorized') return reply(401, {error: 'mock_unauthorized'});
  if (req.url === '/usage-limited') return reply(429, {error: 'mock_rate_limit'});
  if (req.url === '/usage-timeout') return setTimeout(() => reply(503, {error: 'mock_timeout'}), 12000);
  if (req.url === '/usage-fail') return reply(503, {error: 'mock_unavailable'});
  if (req.url === '/usage-bad-ack') return reply(200, {accepted: true, event_id: 'wrong'});
  const fields = ['event_id', 'occurred_at', 'environment', 'conversation_id', 'request_id',
    'business_action', 'model', 'input_tokens', 'output_tokens',
    'cached_input_tokens', 'reasoning_tokens', 'status'];
  if (!body || fields.some(key => !(key in body)) || Object.keys(body).some(key => !fields.includes(key))) {
    return reply(400, {error: 'contract_mismatch'});
  }
  const previous = events.get(body.event_id);
  if (previous && JSON.stringify(previous) !== JSON.stringify(body)) return reply(409, {error: 'event_conflict'});
  events.set(body.event_id, body);
  return reply(200, {accepted: true, event_id: body.event_id});
});
server.listen(Number(process.env.MOCK_USAGE_PORT || 0), '127.0.0.1', () => {
  process.stdout.write(JSON.stringify({base_url: `http://127.0.0.1:${server.address().port}`}) + '\n');
});
process.on('SIGTERM', () => server.close(() => process.exit(0)));
