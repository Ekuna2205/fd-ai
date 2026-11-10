const ACCESS = 'faceguard.token'
const REFRESH = 'faceguard.refresh'

// sessionStorage: cleared when the tab closes and never shared between tabs. Access is wrapped because storage can be
// unavailable (private mode, blocked cookies). Note: any script running on the page could read these values, which is
// why the app ships a strict Content-Security-Policy (see infrastructure/nginx) and renders no untrusted HTML.
const read = (k: string) => { try { return sessionStorage.getItem(k) } catch { return null } }
const write = (k: string, v: string) => { try { sessionStorage.setItem(k, v) } catch { /* user signs in again on reload */ } }
const drop = (k: string) => { try { sessionStorage.removeItem(k) } catch { /* ignore */ } }

export const tokenStore = {
  get: () => read(ACCESS),
  getRefresh: () => read(REFRESH),
  set(access: string, refresh?: string) { write(ACCESS, access); if (refresh) write(REFRESH, refresh) },
  clear() { drop(ACCESS); drop(REFRESH) },
}
