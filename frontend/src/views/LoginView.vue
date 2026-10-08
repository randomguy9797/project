<template>
  <div class="card">
    <h1 class="app-title">Login Page</h1>

    <div v-if="error" class="alert alert-error" role="alert">{{ error }}</div>

    <form @submit.prevent="submit" novalidate>
      <div class="field">
        <label for="username">Username</label>
        <input
          id="username"
          v-model="username"
          type="text"
          autocomplete="username"
          required
          maxlength="150"
        />
      </div>

      <div class="field">
        <label for="password">Password</label>
        <input
          id="password"
          v-model="password"
          type="password"
          autocomplete="current-password"
          required
        />
      </div>

      <button type="submit" class="btn btn-primary" :disabled="loading">
        {{ loading ? 'Logging in…' : 'Login' }}
      </button>
    </form>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { apiPost } from '../api/client.js'

const router = useRouter()
const username = ref('')
const password = ref('')
const error = ref(null)
const loading = ref(false)

async function submit() {
  error.value = null
  loading.value = true
  try {
    const fd = new FormData()
    fd.append('username', username.value)
    fd.append('password', password.value)
    const data = await apiPost('/login', fd)
    router.push(data.is_admin ? '/admin' : '/form')
  } catch (e) {
    error.value = e?.error ?? 'An unexpected error occurred.'
  } finally {
    loading.value = false
  }
}
</script>
