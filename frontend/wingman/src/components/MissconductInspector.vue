<script setup>
import VerticalDevider from './VerticalDevider.vue';
import Container1 from './Container1.vue';
import MissconductExplorer from './MissconductExplorer.vue';
import MissconductCounter from './MissconductCounter.vue';
import MissconductDetailsViewer from './MissconductDetailsViewer.vue';
</script>

<template>
    <div class="title">
        Human safety system
    </div>

    <div class="splitview">
      <div class="leftside">
        <Container1>
          <MissconductExplorer />
        </Container1>
        <Container1>
          <MissconductCounter/>
        </Container1>
      </div>
      <VerticalDevider />
      <div class="details">
        <Container1>
          <MissconductDetailsViewer id="https://picsum.phosadfffsdftos/200/300"/>
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
}

.splitview {
  margin-top: 1rem;
  justify-content: center;
  width: min-content;
  display: flex;
  flex-direction: row;
}
</style>
