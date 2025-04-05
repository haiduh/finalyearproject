// // GameInfoParser.ts
// export interface GameInfo {
//     title: string;
//     game: string;
//     keyDetails: string;
//     requiredItems: string;
//     instructions: string[];
//     proTips: string[];
//   }
  
//   export function parseGameInfo(question: string, gameName: string, response: string): GameInfo {
//     // Default structure
//     const gameInfo: GameInfo = {
//       title: question,
//       game: gameName,
//       keyDetails: "",
//       requiredItems: "",
//       instructions: [],
//       proTips: []
//     };
  
//     // Extract key details (after 📌 Key Details:)
//     const keyDetailsMatch = response.match(/📌 Key Details:(.*?)(?=🛠️|$)/s);
//     if (keyDetailsMatch && keyDetailsMatch[1]) {
//       gameInfo.keyDetails = keyDetailsMatch[1].trim();
//     }
  
//     // Extract required items (after 🛠️ Required Items/Mechanics:)
//     const requiredItemsMatch = response.match(/🛠️ Required Items\/Mechanics:(.*?)(?=🗺️|$)/s);
//     if (requiredItemsMatch && requiredItemsMatch[1]) {
//       gameInfo.requiredItems = requiredItemsMatch[1].trim();
//     }
  
//     // Extract instructions (after 🗺️ Step-by-Step Instructions:)
//     const instructionsMatch = response.match(/🗺️ Step-by-Step Instructions:(.*?)(?=💡|$)/s);
//     if (instructionsMatch && instructionsMatch[1]) {
//       // Split by numbered points (1., 2., 3., etc.)
//       const instructionsList = instructionsMatch[1].trim()
//         .split(/\d+\.\s+/)
//         .filter(item => item.trim() !== "");
      
//       gameInfo.instructions = instructionsList;
//     }
  
//     // Extract pro tips (after 💡 Pro Tips:)
//     const proTipsMatch = response.match(/💡 Pro Tips:(.*?)(?=$)/s);
//     if (proTipsMatch && proTipsMatch[1]) {
//       // Split by bullet points
//       const proTipsList = proTipsMatch[1].trim()
//         .split(/- /)
//         .filter(item => item.trim() !== "");
      
//       gameInfo.proTips = proTipsList;
//     }
  
//     return gameInfo;
//   }