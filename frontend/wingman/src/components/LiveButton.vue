<script setup>
import { defineEmits} from 'vue';

function openlink() {
  // change live ip here
  window.open("http://localhost:8000/liveview", "_blank");
}
const emit = defineEmits(['click'])
</script>
<template>
	<button class="live-button" type="button" @click=openlink>
		<div>
			Go LIVE
		</div>


	</button>
</template>



<style scoped>


@keyframes pulse {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(160, 13, 13, 0.7);
  }
  50% {
    box-shadow: 0 0 0 8px rgba(160, 13, 13, 0);
  }
}

.live-button {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  border: 1px solid var(--color-border);
  background: transparent;
  color: var(--text);
  padding: 0.5rem 0.8rem;
  border-radius: 12px;
  cursor: pointer;
  font-weight: 600;
  margin-left: 0.5rem;
  margin-top: 0.5rem;
  position: fixed;
  top: 1rem;
  right: 1rem;
  transition: all 0.3s ease;
}

.live-button:hover {
	background: #a00d0d;
  animation: pulse 1.5s infinite;
  transform: scale(1.05);
}

.live-button:active {
    background: #a00d0d;
  transform: scale(0.98);
}
</style>
