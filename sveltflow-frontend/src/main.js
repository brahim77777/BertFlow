import App from './App.svelte'
import './app.css'
import '@xyflow/svelte/dist/style.css';

const app = new App({
  target: document.getElementById('app'),
})

export default app
