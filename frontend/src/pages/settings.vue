<template>
  <div class="container-page space-y-5">
    <header>
      <h1 class="page-title">Settings</h1>
      <p class="text-secondary mt-1">Manage your account details and password.</p>
    </header>

    <!-- The admin principal has no editable profile. -->
    <SectionCard v-if="auth.isAdmin" title="Administrator" icon="i-carbon-user-admin">
      <p class="text-body">You are signed in as the administrator (<span class="font-mono">__token__</span>). The admin credential is managed through the deployment configuration, not this page.</p>
    </SectionCard>

    <template v-else>
      <SectionCard title="Profile" icon="i-carbon-user-profile">
        <form class="space-y-3 max-w-lg" @submit.prevent="saveProfile">
          <KField label="Username" hint="Your panel login name.">
            <KInput v-model="profile.username" placeholder="username" />
          </KField>
          <KField label="Display name" hint="Shown around the panel.">
            <KInput v-model="profile.display_name" placeholder="Your name" />
          </KField>
          <KField label="Default machine account" hint="Preferred Unix account name on managed machines. Used as the default target when you request access. Leave empty to use your username.">
            <KInput v-model="profile.default_account" placeholder="e.g. jsmith" />
          </KField>
          <div class="flex justify-end">
            <KButton variant="primary" :loading="savingProfile" @click="saveProfile"> Save profile </KButton>
          </div>
        </form>
      </SectionCard>

      <SectionCard title="Password" icon="i-carbon-password">
        <form class="space-y-3 max-w-lg" @submit.prevent="savePassword">
          <KField label="Current password">
            <KInput v-model="pw.old_password" type="password" placeholder="Current password" />
          </KField>
          <KField label="New password">
            <KInput v-model="pw.new_password" type="password" placeholder="New password" />
          </KField>
          <KField label="Confirm new password">
            <KInput v-model="pw.confirm" type="password" placeholder="Repeat new password" />
          </KField>
          <div class="flex justify-end">
            <KButton variant="primary" :loading="savingPassword" :disabled="!pwReady" @click="savePassword"> Change password </KButton>
          </div>
        </form>
      </SectionCard>
    </template>
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted } from "vue"

import { ElMessage } from "element-plus"

import KButton from "@/components/common/KButton.vue"
import KField from "@/components/common/KField.vue"
import KInput from "@/components/common/KInput.vue"
import SectionCard from "@/components/common/SectionCard.vue"
import { useAuthStore } from "@/stores/auth"

const auth = useAuthStore()

const profile = reactive({ username: "", display_name: "", default_account: "" })
const pw = reactive({ old_password: "", new_password: "", confirm: "" })
const savingProfile = ref(false)
const savingPassword = ref(false)

const pwReady = computed(() => pw.old_password && pw.new_password && pw.new_password === pw.confirm)

function syncProfile() {
  profile.username = auth.name
  profile.display_name = auth.me?.display_name || ""
  profile.default_account = auth.defaultAccount
}

async function saveProfile() {
  savingProfile.value = true
  try {
    await auth.updateProfile({
      username: profile.username.trim(),
      display_name: profile.display_name.trim(),
      default_account: profile.default_account.trim(),
    })
    ElMessage.success("Profile updated")
    syncProfile()
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to update profile")
  } finally {
    savingProfile.value = false
  }
}

async function savePassword() {
  if (pw.new_password !== pw.confirm) {
    ElMessage.warning("New passwords do not match")
    return
  }
  savingPassword.value = true
  try {
    await auth.changePassword({
      old_password: pw.old_password,
      new_password: pw.new_password,
    })
    ElMessage.success("Password changed")
    pw.old_password = ""
    pw.new_password = ""
    pw.confirm = ""
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to change password")
  } finally {
    savingPassword.value = false
  }
}

onMounted(syncProfile)
</script>
