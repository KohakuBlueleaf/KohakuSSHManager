/**
 * API client for the KohakuSSHManager backend.
 *
 * One axios instance with an empty baseURL; the request interceptor
 * prepends ``/api`` to every relative path so callers write the bare
 * route (``keysAPI.list()`` → ``GET /api/keys``). The dev server proxies
 * ``/api`` to the FastAPI process (see vite.config.js); in production the
 * same process serves both the SPA and the API, so relative URLs work
 * unchanged.
 *
 * Auth is cookie-based (``ksm_session``, HttpOnly) — nothing to inject
 * here. On a 401 for any normal request the session has expired, so we
 * reset the auth store and bounce to /login. The boot probe (/auth/me)
 * and the login/logout calls are excluded so they can handle their own
 * outcome without a redirect fighting the router guard.
 *
 * snake_case field names stay on the wire; components read them directly.
 */

import axios from "axios"

const api = axios.create({
  baseURL: "",
  timeout: 30000,
})

api.interceptors.request.use((config) => {
  const path = config.url || ""
  if (!/^https?:\/\//.test(path)) {
    config.url = path.startsWith("/") ? `/api${path}` : `/api/${path}`
  }
  return config
})

// Requests whose 401 should NOT trigger a redirect (they own their flow).
const AUTH_SELF = ["/auth/me", "/auth/login", "/auth/logout"]

api.interceptors.response.use(
  (resp) => resp,
  async (error) => {
    const status = error?.response?.status
    const url = error?.config?.url || ""
    if (status === 401 && !AUTH_SELF.some((p) => url.includes(p))) {
      // Lazy import to avoid a load-time cycle (store imports this module).
      try {
        const { useAuthStore } = await import("@/stores/auth")
        useAuthStore().reset()
      } catch {
        // Pinia not ready (very early failure) — fall through to redirect.
      }
      if (window.location.pathname !== "/login") {
        window.location.assign("/login")
      }
    }
    return Promise.reject(error)
  },
)

/** Auth + session */
export const authAPI = {
  async login(body) {
    const { data } = await api.post("/auth/login", body)
    return data
  },
  async logout() {
    await api.post("/auth/logout")
  },
  async me() {
    const { data } = await api.get("/auth/me")
    return data
  },
  async changePassword(body) {
    const { data } = await api.post("/auth/password", body)
    return data
  },
}

/** Panel users (admin) */
export const usersAPI = {
  async list() {
    const { data } = await api.get("/users")
    return data
  },
  async create(body) {
    const { data } = await api.post("/users", body)
    return data
  },
  async update(id, body) {
    const { data } = await api.patch(`/users/${id}`, body)
    return data
  },
  async remove(id) {
    const { data } = await api.delete(`/users/${id}`)
    return data
  },
}

/** SSH public keys */
export const keysAPI = {
  async list(params = {}) {
    const { data } = await api.get("/keys", { params })
    return data
  },
  async create(body) {
    const { data } = await api.post("/keys", body)
    return data
  },
  async revoke(id) {
    const { data } = await api.post(`/keys/${id}/revoke`)
    return data
  },
  async assign(id, userId) {
    const { data } = await api.post(`/keys/${id}/assign`, { user_id: userId })
    return data
  },
  async remove(id) {
    const { data } = await api.delete(`/keys/${id}`)
    return data
  },
}

/** Machines + local accounts + enroll/init */
export const machinesAPI = {
  async list() {
    const { data } = await api.get("/machines")
    return data
  },
  async create(body) {
    const { data } = await api.post("/machines", body)
    return data
  },
  async get(id) {
    const { data } = await api.get(`/machines/${id}`)
    return data
  },
  async update(id, body) {
    const { data } = await api.patch(`/machines/${id}`, body)
    return data
  },
  async remove(id) {
    const { data } = await api.delete(`/machines/${id}`)
    return data
  },
  async managementKey() {
    const { data } = await api.get("/machines/management-key")
    return data
  },
  async enroll(id) {
    const { data } = await api.post(`/machines/${id}/enroll`)
    return data
  },
  async enrollConfirm(id, fingerprint) {
    const { data } = await api.post(`/machines/${id}/enroll/confirm`, { fingerprint })
    return data
  },
  async refresh(id) {
    const { data } = await api.post(`/machines/${id}/refresh`)
    return data
  },
  async accounts(id) {
    const { data } = await api.get(`/machines/${id}/accounts`)
    return data
  },
  async initPreview(id) {
    const { data } = await api.post(`/machines/${id}/init/preview`)
    return data
  },
  async initApply(id, usernames) {
    const { data } = await api.post(`/machines/${id}/init/apply`, { usernames })
    return data
  },
  // Local-account actions (routed under /accounts on the backend).
  async adoptAccount(accountId, userId) {
    const { data } = await api.post(`/accounts/${accountId}/adopt`, { user_id: userId })
    return data
  },
  async unlinkAccount(accountId) {
    const { data } = await api.post(`/accounts/${accountId}/unlink`)
    return data
  },
  async deleteAccount(accountId, { deleteHome = false, confirm }) {
    const { data } = await api.delete(`/accounts/${accountId}`, {
      params: { delete_home: deleteHome },
      data: { confirm },
    })
    return data
  },
  async setAccountGroups(accountId, { add = [], remove = [] }) {
    const { data } = await api.post(`/accounts/${accountId}/groups`, { add, remove })
    return data
  },
}

/** Access requests + grants */
export const accessAPI = {
  async createRequest(body) {
    const { data } = await api.post("/access/requests", body)
    return data
  },
  async listRequests(params = {}) {
    const { data } = await api.get("/access/requests", { params })
    return data
  },
  async approve(id) {
    const { data } = await api.post(`/access/requests/${id}/approve`)
    return data
  },
  async reject(id, reason) {
    const { data } = await api.post(`/access/requests/${id}/reject`, { reason })
    return data
  },
  async revoke(id) {
    const { data } = await api.post(`/access/requests/${id}/revoke`)
    return data
  },
  async overview() {
    const { data } = await api.get("/access/overview")
    return data
  },
}

/** Remote actions (poll targets) */
export const actionsAPI = {
  async list(params = {}) {
    const { data } = await api.get("/actions", { params })
    return data
  },
  async get(id) {
    const { data } = await api.get(`/actions/${id}`)
    return data
  },
  async retry(id) {
    const { data } = await api.post(`/actions/${id}/retry`)
    return data
  },
}

/** Groups (admin) */
export const groupsAPI = {
  async list() {
    const { data } = await api.get("/groups")
    return data
  },
  async create(body) {
    const { data } = await api.post("/groups", body)
    return data
  },
  async update(id, body) {
    const { data } = await api.patch(`/groups/${id}`, body)
    return data
  },
  async remove(id) {
    const { data } = await api.delete(`/groups/${id}`)
    return data
  },
  async addMember(id, userId) {
    const { data } = await api.post(`/groups/${id}/members/${userId}`)
    return data
  },
  async removeMember(id, userId) {
    const { data } = await api.delete(`/groups/${id}/members/${userId}`)
    return data
  },
  async addMachine(id, machineId) {
    const { data } = await api.post(`/groups/${id}/machines/${machineId}`)
    return data
  },
  async removeMachine(id, machineId) {
    const { data } = await api.delete(`/groups/${id}/machines/${machineId}`)
    return data
  },
}

/** Storage mounts + usage */
export const storageAPI = {
  async listMounts() {
    const { data } = await api.get("/storage/mounts")
    return data
  },
  async createMount(body) {
    const { data } = await api.post("/storage/mounts", body)
    return data
  },
  async updateMount(id, body) {
    const { data } = await api.patch(`/storage/mounts/${id}`, body)
    return data
  },
  async removeMount(id) {
    const { data } = await api.delete(`/storage/mounts/${id}`)
    return data
  },
  async scan(id) {
    const { data } = await api.post(`/storage/mounts/${id}/scan`)
    return data
  },
  async usage(id) {
    const { data } = await api.get(`/storage/mounts/${id}/usage`)
    return data
  },
  async mine() {
    const { data } = await api.get("/storage/usage/mine")
    return data
  },
}

/** Admin overview + audit + webhook */
export const adminAPI = {
  async overview() {
    const { data } = await api.get("/admin/overview")
    return data
  },
  async audit(params = {}) {
    const { data } = await api.get("/admin/audit", { params })
    return data
  },
  async webhookTest() {
    const { data } = await api.post("/admin/webhook/test")
    return data
  },
}

export default api
