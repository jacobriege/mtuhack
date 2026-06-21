<script setup>
import Button1 from './button1.vue';
import { defineProps } from 'vue';

const props = defineProps({
  violationId: {
    type: [String, Number],
    default: null,
  },
  flagged: {
    type: Boolean,
    default: false,
  }
})

// Toggles flagged status for the selected violation.
async function flagMisconduct() {
  const response = await fetch(`http://localhost:5000/violations/instance/flag?set=${!props.flagged}&violationId=${props.violationId}`)
  if (!response.ok) {
    throw new Error(`Flag request failed: ${response.status}`);
  }
}
</script>

<template>
   <Button1 @click="flagMisconduct" :class="['button1', { active: props.flagged }]">
        Flag missconduct
   </Button1>
</template>

<style scoped>
.button1 {
  border-radius: 12px;
  width: fit-content;
  background: var(--secondary);
  color: var(--color-background);
}
.active {
  background: var(--color-background);
  color: var(--color-heading)
}

</style>
