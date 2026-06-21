console.log('Initializing WebSocket integration...')
import {ref} from 'vue'
const messages = ref([])
let socket = null

const onmount = (data) => {
  console.log('Connecting to WebSocket...')
  socket = new WebSocket('ws://localhost:5000/violations/ws')

  socket.onopen = () => {
    console.log('Connected')
    socket.send('Hello server!')
  }

  socket.onmessage = (event) => {
    messages.value.push(event.data)

    data.value.updatecounter += 1
  }

  socket.onerror = (error) => {
    console.error('WebSocket error:', error)
  }

  socket.onclose = () => {
    console.log('Disconnected')
  }
}
const onunmount = () => {
  if (socket) {
    socket.close()
  }
}

export default {
  messages,
  onmount,
  onunmount
}