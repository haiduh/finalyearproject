// // src/GameInfoDisplay.tsx
// import React from 'react';
// import { GameInfo } from './GameInfoParser';
// import './App.css';

// interface GameInfoDisplayProps {
//   info: GameInfo;
// }

// const GameInfoDisplay: React.FC<GameInfoDisplayProps> = ({ info }) => {
//   // Helper function to convert markdown-style bold to HTML
//   const formatText = (text: string) => {
//     return { __html: text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') };
//   };

//   return (
//     <div className="game-info-card bg-gray-800 text-white p-4 rounded-lg max-w-2xl mx-auto shadow-lg">
//       <div className="game-header border-b border-gray-600 pb-2 mb-4">
//         <h2 className="text-xl font-bold">{info.title}</h2>
//         <div className="game-badge bg-blue-600 text-xs px-2 py-1 rounded inline-block mt-1">
//           {info.game}
//         </div>
//       </div>

//       {info.keyDetails && (
//         <div className="info-section mb-4">
//           <div className="section-header flex items-center mb-2">
//             <span className="mr-2 text-yellow-400">📌</span>
//             <h3 className="font-semibold">Key Details</h3>
//           </div>
//           <p className="pl-6" dangerouslySetInnerHTML={formatText(info.keyDetails)}></p>
//         </div>
//       )}

//       {info.requiredItems && (
//         <div className="info-section mb-4">
//           <div className="section-header flex items-center mb-2">
//             <span className="mr-2 text-yellow-400">🛠️</span>
//             <h3 className="font-semibold">Required Items/Mechanics</h3>
//           </div>
//           <p className="pl-6" dangerouslySetInnerHTML={formatText(info.requiredItems)}></p>
//         </div>
//       )}

//       {info.instructions.length > 0 && (
//         <div className="info-section mb-4">
//           <div className="section-header flex items-center mb-2">
//             <span className="mr-2 text-yellow-400">🗺️</span>
//             <h3 className="font-semibold">Step-by-Step Instructions</h3>
//           </div>
//           <ol className="pl-6 space-y-2">
//             {info.instructions.map((instruction, index) => (
//               <li key={index} className="instruction" dangerouslySetInnerHTML={formatText(instruction)}></li>
//             ))}
//           </ol>
//         </div>
//       )}

//       {info.proTips.length > 0 && (
//         <div className="info-section">
//           <div className="section-header flex items-center mb-2">
//             <span className="mr-2 text-yellow-400">💡</span>
//             <h3 className="font-semibold">Pro Tips</h3>
//           </div>
//           <ul className="pl-6 space-y-2">
//             {info.proTips.map((tip, index) => (
//               <li key={index} className="tip" dangerouslySetInnerHTML={formatText(tip)}></li>
//             ))}
//           </ul>
//         </div>
//       )}
//     </div>
//   );
// };

// export default GameInfoDisplay;