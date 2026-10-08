import { createRouter, createWebHistory } from 'vue-router'
import { apiGet } from '../api/client.js'

import LoginView from '../views/LoginView.vue'
import FormView from '../views/FormView.vue'
import SuccessView from '../views/SuccessView.vue'
import AdminView from '../views/AdminView.vue'
import ForbiddenView from '../views/errors/ForbiddenView.vue'
import NotFoundView from '../views/errors/NotFoundView.vue'

const routes = [
  { path: '/',        redirect: '/login' },
  { path: '/login',   component: LoginView,   meta: { public: true } },
  { path: '/form',    component: FormView,    meta: { requiresAuth: true } },
  { path: '/success', component: SuccessView, meta: { requiresAuth: true } },
  { path: '/admin',   component: AdminView,   meta: { requiresAuth: true, requiresAdmin: true } },
  { path: '/403',     component: ForbiddenView, meta: { public: true } },
  { path: '/:pathMatch(.*)*', component: NotFoundView, meta: { public: true } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  if (to.meta.public) return true

  let user
  try {
    user = await apiGet('/me')
  } catch {
    return '/login'
  }

  if (to.meta.requiresAdmin && !user.is_admin) {
    return '/403'
  }

  return true
})

export default router
