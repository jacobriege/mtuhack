<script setup>
import { ref } from 'vue';
const newtotalcount = ref(100);
const missconducts = ref([
    { id: 1, type: 'Without Helm', date: '1.6.2024', time: '14:30' },
    { id: 2, type: 'Zone Missconduct', date: '1.6.2024', time: '15:00' },
    { id: 3, type: 'Laying down', date: '1.6.2024', time: '15:30' },
]);
</script>

<template>
  <div class="missconduct-explorer">
    <div class="topline">
        <div class="title">{{ newtotalcount }} new missconducts </div>
        <div class="filter">
            <Icon></Icon>
            <div>Filter</div>
        </div>
    </div>
    <Divider />
    <div class="missconducts">
        <div if="missconducts.length === 0" class="empty">No new missconducts detected</div>
        <div if="missconducts.length > 0" v-for="missconduct in missconducts" :key="missconduct.id" class="missconduct">
            <div class="type">{{ missconduct.type }}</div>
            <div class="time">{{ missconduct.time }}</div>
            <div class="date">{{ missconduct.date }}</div>
        </div>
    </div>
  </div>
</template>

<style scoped>
.missconduct-explorer {
  display: flex;
  flex-direction: column;
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
.missconducts {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  height: 300px;
  overflow-y: auto;
}
.missconduct {
  border-radius: 8px;
  padding: 0.8rem;
  display: flex;
  justify-content: space-between;
  background-color: var(--primary);
}
.missconduct:active {
  background-color: var(--primary-hover);
  border: 1px solid var(--color-border);
}

.topline {
  padding: 0.5rem;
  padding-bottom: 1rem;
  display: flex;
  justify-content: space-between;
  gap: 1rem;
}

.filter {
  display: flex;
  place-items: center;
  gap: 0.4rem;
}


</style>
