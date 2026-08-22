<script setup>
</script>

<template>
  <div class="app">
    <nav class="nav">
      <span class="brand">doit-voc-agent</span>
      <div class="links">
        <RouterLink to="/">VOC 챗</RouterLink>
        <RouterLink to="/dashboard">대시보드</RouterLink>
      </div>
    </nav>
    <RouterView />
  </div>
</template>
