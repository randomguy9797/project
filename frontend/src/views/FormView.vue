<template>
  <div>
    <!-- Sticky payment warning banner (shown while filling form with 1-2 unpaid) -->
    <div
      v-if="paymentStatusLoaded && unpaidCount > 0 && !paymentBlocked"
      class="payment-banner"
      role="alert"
      aria-live="polite"
    >
      ⚠ PAYMENT DUE: Fees for your previous {{ unpaidCount === 1 ? '1 form is' : `${unpaidCount} forms are` }} pending.
    </div>

    <!-- Payment warning popup modal -->
    <div v-if="showPaymentModal" class="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <div class="modal-box">
        <h2 id="modal-title" style="margin-bottom:0.75rem;">Payment Due</h2>
        <p v-if="unpaidCount === 1">Please pay the fees for your previous form.</p>
        <p v-else>Payment for your previous {{ unpaidCount }} forms is pending.</p>
        <p style="margin-top:0.5rem;">You can continue filling this form.</p>
        <button class="btn btn-primary" style="margin-top:1rem;" @click="showPaymentModal = false">OK</button>
      </div>
    </div>

    <!-- Blocked: 3+ unpaid -->
    <div v-if="paymentBlocked" class="card" style="max-width:600px;margin:0 auto;text-align:center;">
      <div style="font-size:2.5rem;margin-bottom:0.75rem;">🚫</div>
      <h2 style="color:#b91c1c;margin-bottom:1rem;">Payment Required</h2>
      <p>You have <strong>{{ unpaidCount }}</strong> previous forms with pending payment.</p>
      <p style="margin-top:0.5rem;">Please contact the administrator and clear the pending fees before creating another form.</p>
      <div class="logout-section">
        <button class="btn btn-secondary" style="display:block;text-align:center;width:100%;" @click="logout">Logout</button>
      </div>
    </div>

    <!-- Normal form (allowed) -->
    <div v-else class="card" style="max-width:600px;margin:0 auto;">

      <!-- Admin-assigned documents panel -->
      <div v-if="availableDocs.length" style="margin-bottom:1.25rem;">
        <p style="font-weight:700;margin-bottom:0.5rem;">Your Documents</p>
        <div v-for="doc in availableDocs" :key="doc.document_key" style="margin-bottom:0.5rem;">
          <div style="display:flex;align-items:center;gap:0.75rem;flex-wrap:wrap;">
            <span style="font-size:0.9rem;">{{ doc.original_filename }}</span>
            <span
              :style="{
                color: doc.downloads >= maxDownloads - 1 ? '#d97706' : '#16a34a',
                fontWeight: 700,
                fontSize: '0.9rem',
              }"
            >
              Downloads: {{ doc.downloads }}/{{ maxDownloads }}
            </span>
            <button
              class="btn btn-primary btn-sm"
              style="width:auto;"
              @click="download(doc.document_key)"
              :disabled="downloading === doc.document_key"
            >
              {{ downloading === doc.document_key ? 'Downloading…' : 'Download' }}
            </button>
          </div>
        </div>
      </div>
      <div v-if="limitedDocs.length" style="margin-bottom:1.25rem;">
        <div v-for="doc in limitedDocs" :key="doc.document_key">
          <span style="color:#dc2626;font-weight:700;font-size:0.9rem;">
            Download limit reached ({{ maxDownloads }}/{{ maxDownloads }})
          </span>
        </div>
      </div>

      <!-- Marquee warning -->
      <div style="overflow:hidden;margin-bottom:1.25rem;">
        <p style="color:#dc2626;font-weight:700;white-space:nowrap;display:inline-block;animation:marquee 40s linear infinite;">
          If Current Energy Bill/Security Deposit Arrears of Consumer &amp; PD Arrears Are Pending of Consumer Error Occurred........ No SERVICES CREATED BY DISCOM SITE
        </p>
      </div>

      <div v-if="error" class="alert alert-error" role="alert">{{ error }}</div>

      <form @submit.prevent="submit" enctype="multipart/form-data" novalidate>

        <!-- WSS Services -->
        <div class="field">
          <label for="wss_service">WSS Services</label>
          <select id="wss_service" v-model="form.wss_service" style="width:100%;padding:0.75rem 1rem;font-size:1rem;border:1.5px solid #d1d5db;border-radius:8px;background:#fafafa;color:#1a1a2e;">
            <option value="">-- Select Service --</option>
            <option v-for="opt in wssOptions" :key="opt" :value="opt">{{ opt }}</option>
          </select>
        </div>

        <!-- Consumer Number -->
        <div class="field">
          <label for="consumer_number">Consumer Number</label>
          <input id="consumer_number" v-model="form.consumer_number" type="text" />
        </div>

        <!-- Consumer Name -->
        <div class="field">
          <label>Consumer Name</label>
          <div style="display:flex;gap:0.5rem;">
            <input v-model="form.consumer_first_name" type="text" placeholder="First Name" style="flex:1;" />
            <input v-model="form.consumer_second_name" type="text" placeholder="Second Name" style="flex:1;" />
            <input v-model="form.consumer_last_name" type="text" placeholder="Last Name" style="flex:1;" />
          </div>
        </div>

        <!-- Application ID -->
        <div class="field">
          <label for="application_id">Application ID</label>
          <input id="application_id" v-model="form.application_id" type="text" />
        </div>

        <!-- Consumer New Name -->
        <div class="field">
          <label>Consumer New Name</label>
          <div style="display:flex;gap:0.5rem;">
            <input v-model="form.new_first_name" type="text" placeholder="First Name" style="flex:1;" />
            <input v-model="form.new_second_name" type="text" placeholder="Second Name" style="flex:1;" />
            <input v-model="form.new_last_name" type="text" placeholder="Last Name" style="flex:1;" />
          </div>
        </div>

        <!-- Email -->
        <div class="field">
          <label for="email">Email</label>
          <input id="email" v-model="form.email" type="email" style="width:100%;padding:0.75rem 1rem;font-size:1rem;border:1.5px solid #d1d5db;border-radius:8px;background:#fafafa;color:#1a1a2e;" />
        </div>

        <!-- Phone Number -->
        <div class="field">
          <label for="mobile_number">Phone Number (Aadhar Linked)</label>
          <input id="mobile_number" v-model="form.mobile_number" type="tel" maxlength="10" inputmode="numeric" pattern="[6-9][0-9]{9}" />
          <span class="hint">10-digit Indian mobile number (starts with 6, 7, 8, or 9)</span>
        </div>

        <!-- Reason for Name Change -->
        <div class="field">
          <label for="reason_name_change">Reason for Name Change</label>
          <select id="reason_name_change" v-model="form.reason_name_change" style="width:100%;padding:0.75rem 1rem;font-size:1rem;border:1.5px solid #d1d5db;border-radius:8px;background:#fafafa;color:#1a1a2e;">
            <option value="">-- Select Reason --</option>
            <option value="Correction in Spelling">Correction in Spelling</option>
            <option value="Change in Ownership">Change in Ownership</option>
          </select>
        </div>

        <!-- Category -->
        <div class="field">
          <label for="category">Category</label>
          <select id="category" v-model="form.category" style="width:100%;padding:0.75rem 1rem;font-size:1rem;border:1.5px solid #d1d5db;border-radius:8px;background:#fafafa;color:#1a1a2e;">
            <option value="">-- Select Category --</option>
            <option v-for="opt in categoryOptions" :key="opt" :value="opt">{{ opt }}</option>
          </select>
        </div>

        <!-- Address -->
        <div class="field">
          <label for="address">Address</label>
          <textarea id="address" v-model="form.address" rows="3" style="width:100%;padding:0.75rem 1rem;font-size:1rem;border:1.5px solid #d1d5db;border-radius:8px;background:#fafafa;color:#1a1a2e;resize:vertical;"></textarea>
        </div>

        <!-- Bank Details -->
        <fieldset style="border:1.5px solid #d1d5db;border-radius:8px;padding:1rem;margin-bottom:1.25rem;">
          <legend style="font-weight:600;padding:0 0.5rem;color:#333;">Bank Details (For SD Refund)</legend>
          <div class="field" style="margin-bottom:1rem;">
            <label for="account_number">Account Number</label>
            <input id="account_number" v-model="form.account_number" type="text" />
          </div>
          <div class="field" style="margin-bottom:0;">
            <label for="ifsc_code">IFSC Code</label>
            <input id="ifsc_code" v-model="form.ifsc_code" type="text" maxlength="11" style="text-transform:uppercase;" />
          </div>
        </fieldset>

        <!-- Document Uploads -->
        <fieldset style="border:1.5px solid #d1d5db;border-radius:8px;padding:1rem;margin-bottom:1.25rem;">
          <legend style="font-weight:600;padding:0 0.5rem;color:#333;">Document Uploads</legend>
          <span class="hint" style="display:block;margin-bottom:0.75rem;">Allowed: PDF, JPG, JPEG &nbsp;|&nbsp; Max size: 10 MB each</span>

          <div v-for="upload in uploadFields" :key="upload.name" class="field">
            <label :for="upload.name">
              {{ upload.label }}
            </label>
            <input
              :id="upload.name"
              type="file"
              accept=".pdf,.jpg,.jpeg"
              @change="e => onFileChange(e, upload.name)"
            />
          </div>
        </fieldset>

        <button type="submit" class="btn btn-primary" :disabled="submitting">
          {{ submitting ? 'Submitting…' : 'Submit' }}
        </button>
      </form>

      <div class="logout-section">
        <button class="btn btn-secondary" style="display:block;text-align:center;width:100%;" @click="logout">Logout</button>
      </div>
    </div>
  </div>
</template>

<style>
  @keyframes marquee {
    0%   { transform: translateX(100vw); }
    100% { transform: translateX(-100%); }
  }

  .payment-banner {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    z-index: 1000;
    background: #fef3c7;
    color: #92400e;
    border-bottom: 2px solid #f59e0b;
    padding: 0.65rem 1rem;
    font-weight: 700;
    font-size: 0.95rem;
    text-align: center;
  }

  .modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.45);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 2000;
    padding: 1rem;
  }

  .modal-box {
    background: #fff;
    border-radius: 12px;
    padding: 2rem 1.75rem;
    max-width: 380px;
    width: 100%;
    box-shadow: 0 8px 32px rgba(0,0,0,0.18);
    text-align: center;
  }
</style>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { apiGet, apiPost } from '../api/client.js'

const router = useRouter()
const error = ref(null)
const submitting = ref(false)
const downloading = ref(null)
const adminDocs = ref([])
const maxDownloads = ref(2)
const unpaidCount = ref(0)
const canSubmit = ref(true)
const showPaymentModal = ref(false)
const paymentStatusLoaded = ref(false)

const MAX_FILE_BYTES = 10 * 1024 * 1024

const wssOptions = [
  'New Connection', 'Change of Name', 'PD Request', 'Load Addition',
  'Address Change', 'Tariff Change', 'SD Refund', 'Solar Load Expansion/Reduction',
]
const categoryOptions = ['Residential', 'Commercial', 'Industrial', 'Other']

const uploadFields = [
  { name: 'upload_aadhar',     label: 'Upload Aadhar' },
  { name: 'upload_pan',        label: 'Upload PAN Card' },
  { name: 'upload_ownership',  label: 'Upload Ownership Document' },
  { name: 'upload_bond',       label: 'Upload Bond' },
  { name: 'upload_energy_bill',label: 'Upload Energy Bill' },
  { name: 'upload_other',      label: 'Upload Other Documents' },
]

const form = ref({
  wss_service: '', consumer_number: '',
  consumer_first_name: '', consumer_second_name: '', consumer_last_name: '',
  application_id: '', new_first_name: '', new_second_name: '', new_last_name: '',
  email: '', mobile_number: '', reason_name_change: '', category: '',
  address: '', account_number: '', ifsc_code: '',
})
const files = ref({})

const limitedDocs = computed(() =>
  adminDocs.value.filter(d => d.downloads >= maxDownloads.value)
)
const availableDocs = computed(() =>
  adminDocs.value.filter(d => d.downloads < maxDownloads.value)
)
const paymentBlocked = computed(() => paymentStatusLoaded.value && unpaidCount.value >= 3)

onMounted(async () => {
  try {
    const data = await apiGet('/form-data')
    adminDocs.value = data.admin_docs || []
    maxDownloads.value = data.max_downloads ?? 2
    unpaidCount.value = data.unpaid_previous_count ?? 0
    canSubmit.value = data.can_submit ?? true
    paymentStatusLoaded.value = true
    if (!paymentBlocked.value && unpaidCount.value > 0) {
      showPaymentModal.value = true
    }
  } catch (e) {
    // An unavailable payment service is not the same as three unpaid forms.
    // Keep the form visible and show the real problem instead of a false
    // "0 forms pending" payment block.
    error.value = e?.error ?? 'Could not verify payment status. Please try again.'
  }
})

function onFileChange(e, fieldName) {
  const file = e.target.files[0]
  if (!file) return
  if (file.size > MAX_FILE_BYTES) {
    e.target.value = ''
    alert(`"${e.target.previousElementSibling.textContent.trim()}" exceeds 10 MB. Please choose a smaller file.`)
    return
  }
  files.value[fieldName] = file
}

async function submit() {
  error.value = null
  submitting.value = true
  try {
    const fd = new FormData()
    Object.entries(form.value).forEach(([k, v]) => fd.append(k, v))
    uploadFields.forEach(({ name }) => {
      if (files.value[name]) fd.append(name, files.value[name])
    })
    await apiPost('/form', fd)
    router.push('/success')
  } catch (e) {
    error.value = e?.error ?? 'We couldn\'t submit your form. Please try again.'
    window.scrollTo(0, 0)
  } finally {
    submitting.value = false
  }
}

async function download(docKey) {
  downloading.value = docKey
  try {
    const fd = new FormData()
    fd.append('doc_key', docKey)
    const res = await apiPost('/download', fd)
    // Trigger browser download from the streamed response
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const cd = res.headers.get('content-disposition') || ''
    const match = cd.match(/filename="?([^"]+)"?/)
    a.download = match ? match[1] : 'document'
    a.click()
    URL.revokeObjectURL(url)
    // Refresh doc list to update counter
    const data = await apiGet('/form-data')
    adminDocs.value = data.admin_docs || []
  } catch (e) {
    error.value = e?.error ?? 'Download failed.'
  } finally {
    downloading.value = null
  }
}

async function logout() {
  await apiGet('/logout')
  router.push('/login')
}
</script>
