<template>
  <div class="card card-success">
    <div class="success-icon" aria-hidden="true">&#10003;</div>
    <h1>Submission Successful</h1>
    <p>Your submission has been received.</p>

    <div class="action-buttons">
      <RouterLink to="/form" class="btn btn-primary">Submit Another</RouterLink>
      <button class="btn btn-secondary" @click="logout">Logout</button>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { apiGet } from '../api/client.js'

const router = useRouter()

async function logout() {
  await apiGet('/logout')
  router.push('/login')
}
</script>
