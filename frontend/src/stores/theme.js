import { defineStore } from "pinia"

const STORAGE_KEY = "ksm-theme"

function storedPreference() {
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

export const useThemeStore = defineStore("theme", {
  state: () => ({
    dark: false,
  }),

  actions: {
    toggle() {
      this.dark = !this.dark
      this.apply()
    },

    apply() {
      document.documentElement.classList.toggle("dark", this.dark)
      try {
        localStorage.setItem(STORAGE_KEY, this.dark ? "dark" : "light")
      } catch {
        // localStorage unavailable (private mode) — theme just won't persist.
      }
    },

    init() {
      const stored = storedPreference()
      if (stored === "dark" || stored === "light") {
        this.dark = stored === "dark"
      } else {
        this.dark = window.matchMedia("(prefers-color-scheme: dark)").matches
      }
      this.apply()
    },
  },
})
