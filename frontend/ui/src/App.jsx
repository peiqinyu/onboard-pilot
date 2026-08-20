import { useState } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from './assets/vite.svg'
import heroImg from './assets/hero.png'
import './App.css'
import { ChatBot } from './ChatBot.tsx';

function App() {
  const [count, setCount] = useState(0)

  return (
    <>
      <section id="center">
        
        <div>
          <ChatBot/>
        </div>
        
      </section>
      <section id="spacer"></section>
    </>
  )
}

export default App
