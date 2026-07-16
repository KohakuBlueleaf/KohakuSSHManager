import pluginVue from "eslint-plugin-vue"
import vuePrettier from "@vue/eslint-config-prettier"

export default [
  ...pluginVue.configs["flat/recommended"],
  vuePrettier,
  {
    rules: {
      "vue/multi-word-component-names": "off",
      "vue/require-explicit-emits": "off",
      "vue/require-prop-types": "off",
      "vue/no-v-html": "warn",
    },
  },
  {
    ignores: ["dist/", "node_modules/"],
  },
]
