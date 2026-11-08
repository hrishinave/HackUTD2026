let onTap = (action) => {
  console.log('tap', action);
  document.getElementById('tap-output').textContent =
    `Last action: ${action} · ${new Date().toLocaleTimeString()}`;
};

function startMediaKeys() {
  const status = document.getElementById('status');
  if (!navigator.mediaSession || typeof MediaMetadata === 'undefined') {
    status.textContent = 'Media keys are unavailable. Use Google Chrome; Ask next and spacebar still log actions.';
    return;
  }

  const silence = document.getElementById('silence');
  silence.volume = 0.01;
  // Start playback inside the click handler so Chrome permits audio.
  const playback = silence.play();
  navigator.mediaSession.metadata = new MediaMetadata({ title: 'Fit Check interview' });
  navigator.mediaSession.playbackState = 'playing';
  navigator.mediaSession.setActionHandler('play', () => onTap('play'));
  navigator.mediaSession.setActionHandler('pause', () => onTap('play'));
  navigator.mediaSession.setActionHandler('nexttrack', () => onTap('next'));
  navigator.mediaSession.setActionHandler('previoustrack', () => onTap('repeat'));

  status.textContent = 'Starting the silent loop…';
  playback.then(() => {
    status.textContent = 'Silent loop playing. Ready for the glasses tap test.';
  }).catch((error) => {
    navigator.mediaSession.playbackState = 'none';
    status.textContent = 'Audio could not start. Click Start interview to retry and report the error.';
    console.error('Silent loop failed:', error);
  });
}

document.getElementById('start').onclick = () => startMediaKeys();
document.getElementById('ask').onclick = () => onTap('play');
document.addEventListener('keydown', (event) => {
  if (event.code !== 'Space' || event.repeat) return;
  // Let focused buttons keep their native keyboard activation.
  const target = event.target;
  if (target && (target.isContentEditable || /^(INPUT|TEXTAREA|SELECT|BUTTON|A)$/.test(target.tagName))) return;
  event.preventDefault();
  onTap('play');
});
