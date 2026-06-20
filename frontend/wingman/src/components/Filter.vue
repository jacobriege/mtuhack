<script setup>
import { ref } from 'vue'

const emit = defineEmits(['applyFilters'])
const showPopup = ref(false)
const startTime = ref('')
const endTime = ref('')
const flaggedOnly = ref(false)

const openPopup = () => {
  showPopup.value = true
}

const closePopup = () => {
  showPopup.value = false
}

const applyFilters = () => {
  emit('applyFilters', {
    startTime: startTime.value,
    endTime: endTime.value,
    flagged: flaggedOnly.value ? true : null,
  })
  closePopup()
}

const resetFilters = () => {
  startTime.value = ''
  endTime.value = ''
  flaggedOnly.value = false
}
</script>

<template>
  <div class="filter-popup-wrapper">
    <button type="button" class="filter-button" @click="openPopup">
      <span class="button-icon">⚙️</span>
      Filter
    </button>

    <div v-if="showPopup" class="overlay" @dblclick.self="closePopup">
      <div class="popup-panel">
        <div class="popup-header">
          <h3>Filter results</h3>
          <button type="button" class="close-button" @click="closePopup">×</button>
        </div>

        <div class="field-row field-row-inline">
          <label>
            Start
            <input type="datetime-local" v-model="startTime" />
          </label>
          <label>
            End
            <input type="datetime-local" v-model="endTime" />
          </label>
        </div>

        <div class="field-row field-row-inline checkbox-row">
          <label class="checkbox-label">
            <input type="checkbox" v-model="flaggedOnly" />
            Flagged only
          </label>
        </div>

        <div class="popup-actions">
          <button type="button" class="apply-button" @click="applyFilters">Apply</button>
          <button type="button" class="secondary-button" @click="resetFilters">Reset</button>
          <button type="button" class="secondary-button" @click="closePopup">Cancel</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.filter-popup-wrapper {
  display: inline-flex;
}

.filter-button {
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
}

.button-icon {
  font-size: 1rem;
}

.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: grid;
  place-items: center;
  padding: 1.5rem;
  z-index: 20;
}

.popup-panel {
  background: var(--color-background-soft);
  border-radius: 18px;
  padding: 1.5rem;
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.16);
}

.popup-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.popup-header h3 {
  margin: 0;
}

.close-button {
  border: none;
  background: transparent;
  color: var(--text);
  font-size: 1.4rem;
  cursor: pointer;
}

.field-row {
  margin-bottom: 1rem;
}

.field-row-inline {
  align-items: center;
  margin-bottom: 1rem;
  width: fit-content;
}

.checkbox-label {
  display: flex !important; 
  flex-direction: row;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.95rem;
  color: var(--text-muted);
}

.field-row label {
  display: grid;
  gap: 0.35rem;
  font-size: 0.95rem;
  color: var(--text-muted);
}

.checkbox-row {
  display: flex;
  align-items: center;
}


.field-row input,
.field-row select {
  width: 100%;
  padding: 0.7rem 0.85rem;
  border-radius: 12px;
  border: 1px solid var(--color-border);
  background: var(--surface-alt);
  color: var(--text);
}



.checkbox-row input[type="checkbox"] {
  width: auto;
  height: auto;
  margin: 0;
  accent-color: var(--accent);
}

.popup-actions {
  display: flex;
  gap: 0.7rem;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.apply-button,
.secondary-button {
  border: none;
  border-radius: 12px;
  padding: 0.7rem 1rem;
  cursor: pointer;
}

.apply-button {
  background: var(--accent);
  color: white;
}

.secondary-button {
  background: var(--surface-alt);
  color: var(--text);
}
</style>
