import { defineStore } from "pinia"

import { authAPI } from "@/utils/api"

// Panel identity store. ``me`` is the shape returned by /api/auth/me and
// /api/auth/login: { name, role, is_admin, display_name }. role is one of
// "admin" | "leader" | "member". A null ``me`` means no valid session.
export const useAuthStore = defineStore("auth", {
  state: () => ({
    me: null,
    loading: false,
  }),

  getters: {
    isAuthenticated: (state) => state.me !== null,
    isAdmin: (state) => !!state.me?.is_admin,
    // Leaders and admins both clear the "leader or above" bar.
    isLeader: (state) => !!state.me && (state.me.role === "leader" || state.me.is_admin),
    role: (state) => state.me?.role ?? null,
    name: (state) => state.me?.name ?? "",
    displayName: (state) => state.me?.display_name || state.me?.name || "",
  },

  actions: {
    async fetchMe() {
      this.loading = true
      try {
        this.me = await authAPI.me()
      } catch {
        // 401 (no session) or a transient error — treat as logged out.
        this.me = null
      } finally {
        this.loading = false
      }
      return this.me
    },

    async login(username, password) {
      // Let the caller surface the error toast; on success cache identity.
      this.me = await authAPI.login({ username, password })
      return this.me
    },

    async logout() {
      try {
        await authAPI.logout()
      } finally {
        this.me = null
      }
    },

    reset() {
      this.me = null
    },
  },
})
