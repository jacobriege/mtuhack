<script setup>
import { ref ,provide, onMounted, onUnmounted, onBeforeMount } from 'vue';
import VerticalDevider from './VerticalDevider.vue';
import Container1 from './Container1.vue';
import MissconductExplorer from './MissconductExplorer.vue';
import MissconductCounter from './MissconductCounter.vue';
import MissconductDetailsViewer from './MissconductDetailsViewer.vue';
import ws from '../js/websocketIntegration.js';
import LiveButton from './LiveButton.vue';


// global vairable missconducts
const data = ref({
  updatecounter: 0,
})
onBeforeMount(() => {
  provide('data', data)
})


// currently selected misconduct for details view
const currentMisconduct = ref(null);
const currentImageUrl = ref(null);

onMounted(() => {ws.onmount(data);})
onUnmounted(() => {ws.onunmount();})


// helper fucntion for fetching instance details
const fetchImageUrl = async (id) => {
  const response = await fetch("http://localhost:5000/violations/instance/image?violationId=" + id)
  if (!response.ok) {
    throw new Error(`Image URL request failed: ${response.status}`);
  }
  const data = await response.json();
  currentImageUrl.value = "http://localhost:5000" + data.imageUrl;
};

// function called when something is selected in the misconduct explorer, emits event to load details
function loadDetails(misconduct) {
  if(misconduct == null) {
    currentMisconduct.value = null;
    currentImageUrl.value = null;
    return;
  }
  currentMisconduct.value = misconduct;
  fetchImageUrl(misconduct.violationId);
  
}



</script>

<template>
    <LiveButton ></LiveButton>
    <div class="complexTitle">
      <div class="title">WINGMAN</div>
      <div class="title2">dashboard</div> 
    </div>
    <Transition name="slideInOut">
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
            <MissconductDetailsViewer v-if="currentImageUrl" :url="currentImageUrl" :misconduct="currentMisconduct"/>
            <div v-else class="empty">Select a misconduct to view details</div>
          </Container1>
        </div>
      </div>
    </Transition>
  

</template>

<style scoped>
.complexTitle {
  display: flex;
  flex-direction: row;
  gap: 0.25rem;
  align-items: baseline;
  width: 75vw;

}

.title {
  font-size: 1.5rem;
  font-weight: 500;
  color: var(--color-heading);
}

.title2 {
  font-size: 1rem;
  font-weight: 200;
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

.empty2 {
  width: 100%;
  height: 50vh;
  display: flex;
  place-items: center;
  justify-content: center;
  text-align: center;
}
.splitview {
  margin: 1rem;
  margin-top: 1rem;
  justify-content: center;
  width: min-content;
  display: flex;
  flex-direction: row;
}

.slideInOut-enter-active,
.slideInOut-leave-active {
  transition: all 0.6s ease;
}

.slideInOut-enter-from,
.slideInOut-leave-to {
  opacity: 0;
  transform: translateY(12px);
  position: absolute;

}
</style>
