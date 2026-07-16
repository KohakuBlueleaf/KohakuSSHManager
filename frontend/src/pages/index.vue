<template>
  <AdminDashboard v-if="auth.isAdmin" />
  <UserDashboard v-else />
</template>

<script setup>
import AdminDashboard from "@/components/dashboard/AdminDashboard.vue"
import UserDashboard from "@/components/dashboard/UserDashboard.vue"
import { useAuthStore } from "@/stores/auth"

const auth = useAuthStore()
</script>
