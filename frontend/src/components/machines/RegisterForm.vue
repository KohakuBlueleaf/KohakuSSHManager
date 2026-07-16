<template>
  <form class="grid grid-cols-1 sm:grid-cols-2 gap-3" @submit.prevent="submit">
    <KField label="Name" required>
      <KInput v-model="form.name" placeholder="e.g. lab-gpu-01" />
    </KField>
    <KField label="Address" required>
      <KInput v-model="form.address" placeholder="hostname or IP" />
    </KField>
    <KField label="SSH port">
      <KInput v-model.number="form.port" type="number" placeholder="22" />
    </KField>
    <KField label="Management user" required>
      <KInput v-model="form.management_user" placeholder="e.g. kohaku" />
    </KField>
    <KField label="Tags" hint="Comma-separated." class="sm:col-span-2">
      <KInput v-model="tagsText" placeholder="gpu, lab, ubuntu" />
    </KField>
    <KField label="Notes" class="sm:col-span-2">
      <KInput v-model="form.notes" type="textarea" :rows="2" placeholder="Optional notes" />
    </KField>
    <div class="sm:col-span-2 flex justify-end">
      <KButton variant="primary" :loading="loading" :disabled="!valid" @click="submit"> Register machine </KButton>
    </div>
  </form>
</template>

<script setup>
import { ref, reactive, computed } from "vue"

import { ElMessage } from "element-plus"

import KButton from "@/components/common/KButton.vue"
import KField from "@/components/common/KField.vue"
import KInput from "@/components/common/KInput.vue"
import { machinesAPI } from "@/utils/api"

const emit = defineEmits(["created"])

const form = reactive({
  name: "",
  address: "",
  port: 22,
  management_user: "",
  notes: "",
})
const tagsText = ref("")
const loading = ref(false)

const valid = computed(() => form.name && form.address && form.management_user)

async function submit() {
  if (!valid.value) return
  loading.value = true
  try {
    const tags = tagsText.value
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean)
    const created = await machinesAPI.create({
      name: form.name.trim(),
      address: form.address.trim(),
      port: form.port || 22,
      management_user: form.management_user.trim(),
      tags,
      notes: form.notes.trim(),
    })
    ElMessage.success("Machine registered")
    form.name = ""
    form.address = ""
    form.port = 22
    form.management_user = ""
    form.notes = ""
    tagsText.value = ""
    emit("created", created)
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || "Failed to register machine")
  } finally {
    loading.value = false
  }
}
</script>
