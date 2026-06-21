<script setup>
import { ref, watch, onBeforeUnmount } from 'vue';
import Flagbutton from './Flagbutton.vue';

const props = defineProps({
  url: {
    type: [String, Number],
    default: null,
  },
  misconduct: {
    type: Object,
    default: null,
  }
});

const imageUrl = ref(null);
const status = ref('idle');
let objectUrl = null;

// Releases any previously created object URL and resets the current image.
const clearImage = () => {
  if (objectUrl) {
    URL.revokeObjectURL(objectUrl);
    objectUrl = null;
  }
  imageUrl.value = null;
};

// Loads misconduct image data from a URL and prepares it for display.
const loadImage = async (url) => {
  clearImage();
  if (url == null || url === '') {
    status.value = 'error';
    return;
  }

  status.value = 'loading';
  try {

    const response = await fetch(`${url}`);
    if (!response.ok) {
      throw new Error(`Image request failed: ${response.status}`);
    }

    const blob = await response.blob();
    if (!blob.type.startsWith('image/')) {
      throw new Error('Expected image data');
    }

    objectUrl = URL.createObjectURL(blob);
    imageUrl.value = objectUrl;
    status.value = 'loaded';
  } catch (error) {
    console.error('Failed to load missconduct image', error);
    status.value = 'error';
  }
};

watch(
  () => props.url,
  (newUrl) => {
    if (newUrl == null || newUrl === '') {
      clearImage();
      status.value = 'error';
      return;
    }
    loadImage(newUrl);
  },
  { immediate: true }
);

onBeforeUnmount(() => {
  clearImage();
});
</script>

<template>
  
  <div class="title">Event Details</div>
  <div class="image-viewer">
    <template v-if="status === 'loaded' && imageUrl">
      <img class="image" :src="imageUrl" alt="Missconduct image" />
    </template>
    <template v-else>
      <div class="empty-state">Sorry image not available<br>:(</div>
    </template>
  </div>
  <!-- <Flagbutton :violationId="props.misconduct?.violationId || 0" :flagged="props.misconduct?.flagged || false"></Flagbutton> -->

  <!-- <MisconductTimeline /> -->
  
</template>

<style scoped>
.flag-button {
  margin-top: 1rem;
  width: 20px;
  height: 20px;
}

.image-viewer {
  margin-top: 1rem;
  padding: 1rem;
  width: 500px;
  height: 300px;
  display: flex;
  place-items: center;
  justify-content: center;
  background-color: var(--primary);
  border-radius: 8px;
}

.image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  border-radius: 4px;
}

.filter {
  display: flex;
  padding: 0.3rem;
  place-items: center;
  gap: 0.4rem;
  border-radius: 10px;
  border: 1px solid var(--color-border);
}
.title {
  font-size: 1.2rem;
  font-weight: 500;
  color: var(--color-heading);

}

.empty-state {
  text-align: center;
  color: var(--color-text);
}

</style>
