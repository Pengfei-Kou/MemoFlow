/**
 * 主题应用：偏好存 localStorage（dark / light / auto），
 * auto 跟随系统日夜切换并监听变化。
 */
const media = window.matchMedia('(prefers-color-scheme: light)')

export function themePref(): string {
  return localStorage.getItem('mf-theme') ?? 'dark'
}

export function applyTheme() {
  const pref = themePref()
  document.documentElement.dataset.theme =
    pref === 'auto' ? (media.matches ? 'light' : 'dark') : pref
}

export function setThemePref(pref: string) {
  localStorage.setItem('mf-theme', pref)
  applyTheme()
}

media.addEventListener('change', () => {
  if (themePref() === 'auto') applyTheme()
})
