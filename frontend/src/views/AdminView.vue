<template>
  <div class="card admin-card" style="max-width:1400px;width:95%;">

    <div class="admin-header">
      <h1>Admin Panel</h1>
    </div>

    <div class="admin-top-grid">

      <!-- Upload Document -->
      <section class="admin-section admin-panel">
        <h2 class="section-title">Upload Document</h2>

        <div v-if="uploadSuccess" class="alert alert-ok" role="status">{{ uploadSuccess }}</div>
        <div v-if="uploadError" class="alert alert-error" role="alert">{{ uploadError }}</div>

        <form @submit.prevent="submitUpload">
          <div class="field">
            <label for="target_username">Username <span class="required">*</span></label>
            <input id="target_username" v-model="uploadForm.target_username" type="text" required placeholder="e.g. vijaybore" />
            <span class="hint">User who will receive access to this document</span>
          </div>
          <div class="field">
            <label for="consumer_number">Consumer Number <span class="required">*</span></label>
            <input id="consumer_number" v-model="uploadForm.consumer_number" type="text" required placeholder="e.g. 123456" />
            <span class="hint">Stored under <code>YYYY/MM/{username}/download/</code></span>
          </div>
          <div class="field">
            <label for="upload_doc">Document <span class="required">*</span></label>
            <input id="upload_doc" type="file" accept=".pdf,.jpg,.jpeg" required @change="e => uploadFile = e.target.files[0]" />
            <span class="hint">PDF, JPG, JPEG &nbsp;|&nbsp; Max 10 MB</span>
          </div>
          <button type="submit" class="btn btn-primary" :disabled="uploading">
            {{ uploading ? 'Uploading…' : 'Upload & Give Access' }}
          </button>
        </form>
      </section>

      <!-- User Management -->
      <section class="admin-section admin-panel">
        <h2 class="section-title">User Management</h2>

        <div v-if="userSuccess" class="alert alert-ok" role="status">{{ userSuccess }}</div>
        <div v-if="userError" class="alert alert-error" role="alert">{{ userError }}</div>

        <div v-if="users.length" class="table-wrap">
          <table class="admin-table">
            <thead>
              <tr><th>Username</th><th>Role</th><th>Status</th><th></th></tr>
            </thead>
            <tbody>
              <tr v-for="u in users" :key="u.username">
                <td><strong>{{ u.username }}</strong></td>
                <td class="muted">{{ u.is_admin ? 'Admin' : 'User' }}</td>
                <td>
                  <span :class="u.is_active ? 'status-active' : 'status-inactive'">
                    {{ u.is_active ? 'Active' : 'Inactive' }}
                  </span>
                </td>
                <td class="td-action">
                  <button class="link-danger" @click="deleteUser(u.username)">Delete</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="user-mgmt-actions">
          <details class="expandable">
            <summary>&#43; Add User</summary>
            <form class="expand-form" @submit.prevent="addUser">
              <div class="field">
                <label>Username <span class="required">*</span></label>
                <input v-model="addForm.username" type="text" required />
              </div>
              <div class="field">
                <label>Password <span class="required">*</span></label>
                <input v-model="addForm.password" type="password" required />
              </div>
              <div class="field field-inline">
                <input id="new_is_admin" v-model="addForm.is_admin" type="checkbox" />
                <label for="new_is_admin">Admin privileges</label>
              </div>
              <button type="submit" class="btn btn-primary btn-sm" :disabled="addingUser">
                {{ addingUser ? 'Adding…' : 'Add User' }}
              </button>
            </form>
          </details>

          <details class="expandable">
            <summary>&#9998; Edit User</summary>
            <form class="expand-form" @submit.prevent="editUser">
              <div class="field">
                <label>Current Username <span class="required">*</span></label>
                <input v-model="editForm.username" type="text" required />
              </div>
              <div class="field">
                <label>New Username <span class="opt">(leave blank to keep)</span></label>
                <input v-model="editForm.new_username" type="text" />
              </div>
              <div class="field">
                <label>New Password <span class="opt">(leave blank to keep)</span></label>
                <input v-model="editForm.new_password" type="password" />
              </div>
              <button type="submit" class="btn btn-primary btn-sm" :disabled="editingUser">
                {{ editingUser ? 'Saving…' : 'Save Changes' }}
              </button>
            </form>
          </details>
        </div>

        <div class="logout-section">
          <button class="btn btn-secondary" style="display:block;text-align:center;width:100%;" @click="logout">Logout</button>
        </div>
      </section>

    </div><!-- /.admin-top-grid -->

    <!-- User Data -->
    <section class="admin-section admin-panel admin-userdata-panel">
      <h2 class="section-title">User Data</h2>

      <!-- Summary table -->
      <div v-if="!showDetail">
        <p v-if="udLoading" class="muted ud-loading">Loading…</p>
        <p v-else-if="udError" class="alert alert-error">{{ udError }}</p>
        <p v-else-if="!udUsers.length" class="muted" style="font-size:0.9rem;">No consumer submissions found.</p>
        <div v-else class="table-wrap">
          <table class="admin-table ud-summary-table">
            <thead>
              <tr><th>Username</th><th>Consumers Created</th><th>Action</th></tr>
            </thead>
            <tbody>
              <tr v-for="u in udUsers" :key="u.username">
                <td><strong>{{ u.username }}</strong></td>
                <td>{{ u.consumer_count }}</td>
                <td class="td-action">
                  <button class="btn-view" @click="loadDetail(u.username)">View</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Consumer detail -->
      <div v-else>
        <div class="ud-detail-header">
          <button class="btn btn-secondary btn-sm" style="width:auto;" @click="showDetail = false">&#8592; Back</button>
          <span class="ud-detail-username">User: {{ detailUsername }}</span>
        </div>
        <p v-if="paymentError" class="alert alert-error">{{ paymentError }}</p>
        <p v-if="detailLoading" class="muted ud-loading">Loading…</p>
        <p v-else-if="detailError" class="alert alert-error">{{ detailError }}</p>
        <p v-else-if="!detailConsumers.length" class="muted" style="font-size:0.9rem;">No consumers found.</p>
        <div v-else class="table-wrap">
          <table class="admin-table consumer-detail-table">
            <thead>
              <tr><th>Consumer No.</th><th>Submitted At</th><th>Name</th><th>Uploaded Documents</th><th>Payment</th><th>Action</th></tr>
            </thead>
            <tbody>
              <template v-for="c in detailConsumers" :key="c.consumer_number">
                <tr v-if="!c.uploaded_files.length">
                  <td class="consumer-num-cell">{{ c.consumer_number }}</td>
                  <td class="muted" style="font-size:0.82rem;white-space:nowrap;">{{ formatDate(c.submitted_at) }}</td>
                  <td class="muted">{{ c.meta.consumer_name || '—' }}</td>
                  <td class="muted">No documents</td>
                  <td>
                    <span :class="c.payment_status === 'PAID' ? 'status-paid' : 'status-unpaid'">
                      {{ c.payment_status || 'N/A' }}
                    </span>
                  </td>
                  <td class="td-action">
                    <button
                      class="btn-pay-action"
                      :class="c.payment_status === 'PAID' ? 'btn-mark-unpaid' : 'btn-mark-paid'"
                      :disabled="paymentUpdating === paymentKey(c)"
                      @click="togglePayment(c)"
                    >
                      {{ paymentUpdating === paymentKey(c) ? '…' : (c.payment_status === 'PAID' ? 'Mark Unpaid' : 'Mark Paid') }}
                    </button>
                  </td>
                </tr>
                <template v-else>
                  <tr v-for="(f, idx) in c.uploaded_files" :key="f.key">
                    <td v-if="idx === 0" :rowspan="c.uploaded_files.length" class="consumer-num-cell">{{ c.consumer_number }}</td>
                    <td v-if="idx === 0" :rowspan="c.uploaded_files.length" class="muted" style="font-size:0.82rem;white-space:nowrap;">{{ formatDate(c.submitted_at) }}</td>
                    <td v-if="idx === 0" :rowspan="c.uploaded_files.length" class="muted name-cell">{{ c.meta.consumer_name || '—' }}</td>
                    <td>
                      <div class="doc-row">
                        <span class="doc-label">{{ f.label }}</span>
                        <span class="doc-filename"> — {{ f.filename }}</span>
                        <span class="doc-actions">
                          <a :href="`/api/admin/consumer-doc?key=${encodeURIComponent(f.key)}&disposition=inline`" target="_blank" class="doc-link doc-link-view">View</a>
                          <a :href="`/api/admin/consumer-doc?key=${encodeURIComponent(f.key)}&disposition=attachment`" class="doc-link doc-link-dl">Download</a>
                        </span>
                      </div>
                    </td>
                    <td v-if="idx === 0" :rowspan="c.uploaded_files.length">
                      <span :class="c.payment_status === 'PAID' ? 'status-paid' : 'status-unpaid'">
                        {{ c.payment_status || 'N/A' }}
                      </span>
                    </td>
                    <td v-if="idx === 0" :rowspan="c.uploaded_files.length" class="td-action">
                      <button
                        class="btn-pay-action"
                        :class="c.payment_status === 'PAID' ? 'btn-mark-unpaid' : 'btn-mark-paid'"
                        :disabled="paymentUpdating === paymentKey(c)"
                        @click="togglePayment(c)"
                      >
                        {{ paymentUpdating === paymentKey(c) ? '…' : (c.payment_status === 'PAID' ? 'Mark Unpaid' : 'Mark Paid') }}
                      </button>
                    </td>
                  </tr>
                </template>
              </template>
            </tbody>
          </table>
        </div>
      </div>
    </section>

  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { apiGet, apiPost } from '../api/client.js'

const router = useRouter()

// ── Upload ──────────────────────────────────────────────────────────────────
const uploadForm = ref({ target_username: '', consumer_number: '' })
const uploadFile = ref(null)
const uploading = ref(false)
const uploadSuccess = ref(null)
const uploadError = ref(null)

async function submitUpload() {
  uploadSuccess.value = null
  uploadError.value = null
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('target_username', uploadForm.value.target_username)
    fd.append('consumer_number', uploadForm.value.consumer_number)
    if (uploadFile.value) fd.append('upload_doc', uploadFile.value)
    const data = await apiPost('/admin/upload', fd)
    uploadSuccess.value = data.message
    uploadForm.value = { target_username: '', consumer_number: '' }
    uploadFile.value = null
  } catch (e) {
    uploadError.value = e?.error ?? 'Upload failed.'
  } finally {
    uploading.value = false
  }
}

// ── Users ────────────────────────────────────────────────────────────────────
const users = ref([])
const userSuccess = ref(null)
const userError = ref(null)
const addingUser = ref(false)
const editingUser = ref(false)
const addForm = ref({ username: '', password: '', is_admin: false })
const editForm = ref({ username: '', new_username: '', new_password: '' })

async function loadUsers() {
  try {
    const data = await apiGet('/admin/users')
    users.value = data.users || []
  } catch {
    // Non-fatal
  }
}

async function addUser() {
  userSuccess.value = null
  userError.value = null
  addingUser.value = true
  try {
    const fd = new FormData()
    fd.append('new_username', addForm.value.username)
    fd.append('new_password', addForm.value.password)
    if (addForm.value.is_admin) fd.append('new_is_admin', '1')
    const data = await apiPost('/admin/user/add', fd)
    userSuccess.value = data.message
    addForm.value = { username: '', password: '', is_admin: false }
    await loadUsers()
  } catch (e) {
    userError.value = e?.error ?? 'Failed to add user.'
  } finally {
    addingUser.value = false
  }
}

async function editUser() {
  userSuccess.value = null
  userError.value = null
  editingUser.value = true
  try {
    const fd = new FormData()
    fd.append('edit_username', editForm.value.username)
    fd.append('edit_new_username', editForm.value.new_username)
    fd.append('edit_new_password', editForm.value.new_password)
    const data = await apiPost('/admin/user/edit', fd)
    userSuccess.value = data.message
    editForm.value = { username: '', new_username: '', new_password: '' }
    await loadUsers()
  } catch (e) {
    userError.value = e?.error ?? 'Failed to edit user.'
  } finally {
    editingUser.value = false
  }
}

async function deleteUser(username) {
  if (!confirm(`Delete user ${username}?`)) return
  userSuccess.value = null
  userError.value = null
  try {
    const fd = new FormData()
    fd.append('del_username', username)
    const data = await apiPost('/admin/user/delete', fd)
    userSuccess.value = data.message
    await loadUsers()
  } catch (e) {
    userError.value = e?.error ?? 'Failed to delete user.'
  }
}

// ── User Data ────────────────────────────────────────────────────────────────
const udLoading = ref(true)
const udError = ref(null)
const udUsers = ref([])
const showDetail = ref(false)
const detailUsername = ref('')
const detailLoading = ref(false)
const detailError = ref(null)
const detailConsumers = ref([])
const paymentUpdating = ref(null)
const paymentError = ref(null)

async function togglePayment(consumer) {
  paymentError.value = null
  const newStatus = consumer.payment_status === 'PAID' ? 'UNPAID' : 'PAID'
  paymentUpdating.value = paymentKey(consumer)
  try {
    const fd = new FormData()
    if (consumer.submission_id) fd.append('submission_id', consumer.submission_id)
    fd.append('username', detailUsername.value)
    fd.append('consumer_number', consumer.consumer_number)
    fd.append('new_status', newStatus)
    const data = await apiPost('/admin/payment', fd)
    consumer.payment_status = data.payment_status
    consumer.submission_id = data.submission_id
  } catch (e) {
    paymentError.value = e?.error ?? 'Failed to update payment status.'
  } finally {
    paymentUpdating.value = null
  }
}

function paymentKey(consumer) {
  return consumer.submission_id ?? `${detailUsername.value}:${consumer.consumer_number}`
}

function formatDate(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
  } catch {
    return iso
  }
}

async function loadUdUsers() {
  udLoading.value = true
  udError.value = null
  try {
    const data = await apiGet('/admin/user-data')
    udUsers.value = data.users || []
  } catch (e) {
    udError.value = e?.error ?? 'Failed to load user data.'
  } finally {
    udLoading.value = false
  }
}

async function loadDetail(username) {
  detailUsername.value = username
  detailConsumers.value = []
  detailError.value = null
  detailLoading.value = true
  showDetail.value = true
  try {
    const data = await apiGet(`/admin/consumer-details?username=${encodeURIComponent(username)}`)
    detailConsumers.value = data.consumers || []
  } catch (e) {
    detailError.value = e?.error ?? 'Failed to load consumer details.'
  } finally {
    detailLoading.value = false
  }
}

async function logout() {
  await apiGet('/logout')
  router.push('/login')
}

onMounted(() => {
  loadUsers()
  loadUdUsers()
})
</script>

<style scoped>
.container {
  max-width: 1400px !important;
  width: 95% !important;
}
body {
  align-items: flex-start !important;
  padding-top: 1.5rem !important;
  padding-bottom: 2rem !important;
}

.status-paid {
  color: #15803d;
  font-weight: 700;
  font-size: 0.85rem;
}

.status-unpaid {
  color: #b91c1c;
  font-weight: 700;
  font-size: 0.85rem;
}

.btn-pay-action {
  display: inline-block;
  font-size: 0.78rem;
  font-weight: 700;
  padding: 0.25rem 0.65rem;
  border-radius: 5px;
  border: 1.5px solid;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s;
}

.btn-mark-paid {
  border-color: #6ee7b7;
  color: #065f46;
  background: #f0fdf4;
}

.btn-mark-paid:hover {
  background: #dcfce7;
}

.btn-mark-unpaid {
  border-color: #fca5a5;
  color: #991b1b;
  background: #fef2f2;
}

.btn-mark-unpaid:hover {
  background: #fee2e2;
}

.btn-pay-action:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
