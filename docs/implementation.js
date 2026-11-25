'use strict';

const links = [...document.querySelectorAll('nav a[href^="#"]')];
const targets = links.map(l => document.querySelector(l.getAttribute('href')));
let lockUntil = 0, activeIdx = 0, spyRaf = 0;
function setActive(i) {
  if (i === activeIdx) return;
  links[activeIdx]?.classList.remove('active');
  links[i]?.classList.add('active');
  activeIdx = i;
}
function spy() {
  spyRaf = 0;
  if (performance.now() < lockUntil) return;
  const atBottom = innerHeight + scrollY >= document.documentElement.scrollHeight - 4;
  let idx = 0;
  if (atBottom) idx = links.length - 1;
  else {
    for (let k = 1; k < targets.length; k++) {
      const t = targets[k];
      if (t && t.getBoundingClientRect().top <= 140) idx = k;
    }
  }
  setActive(idx);
}
links.forEach((l, k) => l.addEventListener('click', () => { setActive(k); lockUntil = performance.now() + 1000; }));
addEventListener('scroll', () => { if (!spyRaf) spyRaf = requestAnimationFrame(spy); }, { passive: true });
