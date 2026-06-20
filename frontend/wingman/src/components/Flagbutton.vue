<script setup>
import Button1 from './button1.vue';

// Placeholder action for a future misconduct flagging workflow.
function flagMisconduct() {
  alert('Misconduct flagged!');
}
</script>

<template>
   <Button1 @click="flagMisconduct">
        Flag missconduct
   </Button1>
</template>

<style scoped>
.button1 {
  padding: 1rem;
  border-radius: 12px;
  background: var(--secondary);
}

</style>
