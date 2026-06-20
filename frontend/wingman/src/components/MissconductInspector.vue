<script setup>
import { ref } from 'vue';
import VerticalDevider from './VerticalDevider.vue';
import Container1 from './Container1.vue';
import MissconductExplorer from './MissconductExplorer.vue';
import MissconductCounter from './MissconductCounter.vue';
import MissconductDetailsViewer from './MissconductDetailsViewer.vue';

// currently selected misconduct for details view
const currentMisconduct = ref(null);
const currentImageUrl = ref(null);

// Updates the selected misconduct state and image URL for the details panel.
function loadDetails(misconduct) {
  if(misconduct == null) {
    currentMisconduct.value = null;
    currentImageUrl.value = null;
    return;
  }
  currentMisconduct.value = misconduct;
  console.log("Selected misconduct", misconduct);
  currentImageUrl.value = misconduct.url;
}
</script>

<template>
    <div class="title">
        Human safety system
    </div>

    <div class="splitview">
      <div class="leftside">
        <Container1>
          <MissconductExplorer @loadDetails="loadDetails" />
        </Container1>
        <Container1>
          <MissconductCounter/>
        </Container1>
      </div>
      <VerticalDevider />
      <div class="details">
        <Container1>
          <MissconductDetailsViewer v-if="currentImageUrl" :id="currentImageUrl" />
          <div v-else class="empty">Select a misconduct to view details</div>
        </Container1>
      </div>
    </div>
  

</template>

<style scoped>
.title {
  font-size: 1.5rem;
  font-weight: 500;
  color: var(--color-heading);
}

.leftside {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  width: 400px;
}
.empty {
  width: 500px;
  height: 300px;
  display: flex;
  place-items: center;
  justify-content: center;
  text-align: center;
}
.splitview {
  margin-top: 1rem;
  justify-content: center;
  width: min-content;
  display: flex;
  flex-direction: row;
}
</style>
