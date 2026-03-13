const state = {
  sessionId: null,
  started: false,
};

const startForm = document.getElementById('start-form');
const messageForm = document.getElementById('message-form');
const chatLog = document.getElementById('chat-log');
const triageChip = document.getElementById('triage-chip');
const triageSummary = document.getElementById('triage-summary');
const updatesView = document.getElementById('updates-view');
const traceView = document.getElementById('trace-view');

function pretty(value) {
  return JSON.stringify(value, null, 2);
}

function appendBubble(role, text) {
  const bubble = document.createElement('div');
  bubble.className = `chat-bubble ${role === '患者' ? 'patient' : 'assistant'}`;
  bubble.innerHTML = `<span class="chat-role">${role}</span><div>${text}</div>`;
  chatLog.appendChild(bubble);
  chatLog.scrollTop = chatLog.scrollHeight;
}

function setTriageView(result) {
  const level = result?.triage_level || '未开始';
  triageChip.textContent = level;
  triageChip.className = 'triage-chip neutral';
  if (level === '红区') triageChip.className = 'triage-chip red';
  if (level === '黄区') triageChip.className = 'triage-chip yellow';
  if (level === '绿区') triageChip.className = 'triage-chip green';

  const flags = (result?.risk_flags || []).join('、') || '暂无';
  const rules = (result?.rule_engine_hits || []).join('；') || '暂无';
  triageSummary.innerHTML = [
    `<div><strong>推荐入口：</strong>${result?.recommended_outpatient_entry || '未生成'}</div>`,
    `<div><strong>是否急诊转运：</strong>${result?.need_emergency_transfer ? '是' : '否'}</div>`,
    `<div><strong>风险标记：</strong>${flags}</div>`,
    `<div><strong>规则命中：</strong>${rules}</div>`,
  ].join('');
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || '请求失败');
  }
  return data;
}

startForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const payload = {
    chief_complaint: document.getElementById('chief_complaint').value.trim(),
    age: Number(document.getElementById('age').value),
    sex: document.getElementById('sex').value,
    temperature: document.getElementById('temperature').value ? Number(document.getElementById('temperature').value) : null,
    pain_score: Number(document.getElementById('pain_score').value),
    vital_signs: {
      heart_rate: Number(document.getElementById('heart_rate').value),
    },
  };

  try {
    const data = await postJson('/session/start', payload);
    state.sessionId = data.session_id;
    state.started = true;
    chatLog.innerHTML = '';
    appendBubble('患者', payload.chief_complaint);
    appendBubble('助手', data.assistant_message);
    setTriageView(data.triage_result);
    updatesView.textContent = pretty({ 首轮建会话: payload });
    traceView.textContent = pretty(data.session_context.last_extraction_trace || { 提示: '首轮会话已创建，等待患者继续描述。' });
  } catch (error) {
    alert(error.message);
  }
});

messageForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!state.started || !state.sessionId) {
    alert('请先开始一个分诊会话。');
    return;
  }

  const input = document.getElementById('message-input');
  const message = input.value.trim();
  if (!message) return;

  try {
    appendBubble('患者', message);
    const data = await postJson('/session/message', {
      session_id: state.sessionId,
      message,
    });
    appendBubble('助手', data.assistant_message);
    setTriageView(data.triage_result);
    updatesView.textContent = pretty(data.extracted_updates);
    traceView.textContent = pretty(data.extraction_trace);
    input.value = '';
  } catch (error) {
    alert(error.message);
  }
});
