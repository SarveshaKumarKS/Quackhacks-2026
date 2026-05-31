/* Quacky landing — playful, dependency-free interactions. */
(() => {
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- floating bubbles ---------- */
  function spawnBubbles() {
    if (reduceMotion) return;
    const layer = document.querySelector('.bubbles');
    if (!layer) return;
    const COUNT = 14;
    for (let i = 0; i < COUNT; i++) {
      const b = document.createElement('span');
      b.className = 'bubble';
      const size = 8 + Math.random() * 34;
      b.style.width = b.style.height = `${size}px`;
      b.style.left = `${Math.random() * 100}vw`;
      b.style.setProperty('--drift', `${(Math.random() * 80 - 40)}px`);
      b.style.animationDuration = `${10 + Math.random() * 16}s`;
      b.style.animationDelay = `${-Math.random() * 20}s`;
      b.style.opacity = (0.25 + Math.random() * 0.4).toFixed(2);
      layer.appendChild(b);
    }
  }

  /* ---------- reveal on scroll ---------- */
  function setupReveal() {
    const els = document.querySelectorAll('.reveal');
    if (!('IntersectionObserver' in window) || reduceMotion) {
      els.forEach(e => e.classList.add('in'));
      return;
    }
    const io = new IntersectionObserver((entries) => {
      entries.forEach(e => {
        if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
      });
    }, { threshold: 0.15 });
    els.forEach(e => io.observe(e));
  }

  /* ---------- synthesized "quack" via Web Audio ---------- */
  let audioCtx;
  function quack() {
    if (reduceMotion) return;
    try {
      audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
      const t = audioCtx.currentTime;
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(620, t);
      osc.frequency.exponentialRampToValueAtTime(230, t + 0.16);
      gain.gain.setValueAtTime(0.0001, t);
      gain.gain.exponentialRampToValueAtTime(0.18, t + 0.03);
      gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.22);
      osc.connect(gain).connect(audioCtx.destination);
      osc.start(t); osc.stop(t + 0.24);
    } catch (_) { /* audio not allowed — no-op */ }
  }

  /* ---------- hero duck: poke = quack + speech bubble + pop ---------- */
  function setupHeroDuck() {
    const duck = document.getElementById('heroDuck');
    const speech = document.getElementById('heroSpeech');
    if (!duck) return;
    const lines = ['Quack! 🦆', 'At your service!', 'Pondering… 💭', 'Ready when you are!', 'Honk? No — quack!'];
    duck.addEventListener('click', () => {
      quack();
      duck.classList.remove('pop'); void duck.offsetWidth; duck.classList.add('pop');
      if (speech) {
        speech.textContent = lines[Math.floor(Math.random() * lines.length)];
        speech.classList.add('show');
        clearTimeout(duck._t);
        duck._t = setTimeout(() => speech.classList.remove('show'), 1600);
      }
    });
  }

  /* ---------- duck-state cards: poke = quack + boing ---------- */
  function setupPokes() {
    document.querySelectorAll('.poke').forEach(img => {
      img.addEventListener('click', () => {
        quack();
        img.classList.remove('boing'); void img.offsetWidth; img.classList.add('boing');
      });
    });
  }

  /* ---------- copy buttons ---------- */
  function setupCopy() {
    document.querySelectorAll('.copy').forEach(btn => {
      btn.addEventListener('click', async () => {
        const text = (btn.dataset.copy || '').replace(/&#10;/g, '\n');
        try { await navigator.clipboard.writeText(text); }
        catch (_) {
          const ta = document.createElement('textarea');
          ta.value = text; document.body.appendChild(ta); ta.select();
          document.execCommand('copy'); ta.remove();
        }
        const old = btn.textContent;
        btn.textContent = 'Copied! ✓'; btn.classList.add('done');
        setTimeout(() => { btn.textContent = old; btn.classList.remove('done'); }, 1600);
      });
    });
  }

  /* ---------- confetti on download ---------- */
  function setupConfetti() {
    const canvas = document.getElementById('confetti');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let pieces = [], raf = null;
    const COLORS = ['#F4A261', '#2C6A4F', '#ffd166', '#e8843a', '#74c69d', '#ffffff'];

    function resize() { canvas.width = innerWidth; canvas.height = innerHeight; }
    resize(); addEventListener('resize', resize);

    function burst() {
      if (reduceMotion) return;
      const n = 140;
      for (let i = 0; i < n; i++) {
        pieces.push({
          x: innerWidth / 2 + (Math.random() - 0.5) * 220,
          y: innerHeight * 0.32,
          vx: (Math.random() - 0.5) * 9,
          vy: Math.random() * -11 - 4,
          g: 0.28 + Math.random() * 0.15,
          size: 6 + Math.random() * 8,
          color: COLORS[(Math.random() * COLORS.length) | 0],
          rot: Math.random() * Math.PI,
          vr: (Math.random() - 0.5) * 0.3,
          life: 0
        });
      }
      if (!raf) raf = requestAnimationFrame(tick);
    }

    function tick() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      pieces.forEach(p => {
        p.vy += p.g; p.x += p.vx; p.y += p.vy; p.rot += p.vr; p.life++;
        ctx.save();
        ctx.translate(p.x, p.y); ctx.rotate(p.rot);
        ctx.fillStyle = p.color;
        ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size * 0.6);
        ctx.restore();
      });
      pieces = pieces.filter(p => p.y < canvas.height + 40 && p.life < 260);
      if (pieces.length) { raf = requestAnimationFrame(tick); }
      else { cancelAnimationFrame(raf); raf = null; ctx.clearRect(0, 0, canvas.width, canvas.height); }
    }

    document.querySelectorAll('a[href$="Quacky-macOS.zip"]').forEach(a => {
      a.addEventListener('click', () => { quack(); burst(); });
    });
  }

  /* ---------- go ---------- */
  document.addEventListener('DOMContentLoaded', () => {
    spawnBubbles();
    setupReveal();
    setupHeroDuck();
    setupPokes();
    setupCopy();
    setupConfetti();
  });
})();
