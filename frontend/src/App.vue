<template>
  <AuthSessionGate>
    <router-view />
  </AuthSessionGate>
</template>

<script setup lang="ts">
import AuthSessionGate from '@/components/AuthSessionGate.vue';
</script>
