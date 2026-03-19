let pollTimer = null;

async function startDownload() {
  const query = document.getElementById('query').value.trim();
  const count = parseInt(document.getElementById('count').value);

  if (!query) { alert('검색어를 입력해주세요'); return; }
  if (!count || count < 1) { alert('장수를 입력해주세요'); return; }

  // UI 전환
  document.getElementById('startBtn').disabled = true;
  document.getElementById('progressCard').style.display = 'block';
  document.getElementById('doneCard').style.display = 'none';
  document.getElementById('errorCard').style.display = 'none';
  document.getElementById('previewGrid').innerHTML = '';
  setProgress(0, count);

  try {
    const res = await fetch('/api/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, count }),
    });
    const { job_id, error } = await res.json();
    if (error) throw new Error(error);

    pollStatus(job_id, count);
  } catch (e) {
    showError(e.message);
  }
}

function pollStatus(jobId, total) {
  pollTimer = setInterval(async () => {
    try {
      const res = await fetch(`/api/status/${jobId}`);
      const job = await res.json();

      setProgress(job.done, job.total || total);

      if (job.status === 'done') {
        clearInterval(pollTimer);
        showDone(jobId);
      } else if (job.status === 'error') {
        clearInterval(pollTimer);
        showError(job.error || '알 수 없는 오류');
      }
    } catch (e) {
      clearInterval(pollTimer);
      showError(e.message);
    }
  }, 800);
}

function setProgress(done, total) {
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  document.getElementById('progressBar').style.width = pct + '%';
  document.getElementById('progressCount').textContent = `${done} / ${total}`;
  document.getElementById('progressLabel').textContent =
    done === 0 ? '이미지 검색 중...' : `다운로드 중... (${pct}%)`;
}

function showDone(jobId) {
  document.getElementById('progressCard').style.display = 'none';
  document.getElementById('doneCard').style.display = 'flex';
  document.getElementById('downloadLink').href = `/api/download/${jobId}`;
}

function showError(msg) {
  document.getElementById('progressCard').style.display = 'none';
  document.getElementById('errorCard').style.display = 'flex';
  document.getElementById('errorText').textContent = msg;
  document.getElementById('startBtn').disabled = false;
}

function reset() {
  if (pollTimer) clearInterval(pollTimer);
  document.getElementById('startBtn').disabled = false;
  document.getElementById('progressCard').style.display = 'none';
  document.getElementById('doneCard').style.display = 'none';
  document.getElementById('errorCard').style.display = 'none';
}

document.getElementById('query').addEventListener('keydown', e => {
  if (e.key === 'Enter') startDownload();
});
