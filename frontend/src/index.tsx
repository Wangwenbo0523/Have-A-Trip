import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import 'tachyons';
import 'aos/dist/aos.css';
import registerServiceWorker from './registerServiceWorker';


const root = ReactDOM.createRoot(document.getElementById('root'))
root.render(<App />)