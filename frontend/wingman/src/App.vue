<script setup>
import MissconductInspector from './components/MissconductInspector.vue'
</script>

<template>
  <main class="c1">
    <div class="centered">
      <MissconductInspector />
    </div>
  </main>
</template>

<style scoped>
header {
  line-height: 1.5;
}
.c1 {
  display: flex;
  justify-content: center;
  flex-direction: column;
  align-items: center;
}
.centered {
  width: min-content;
}
</style>
