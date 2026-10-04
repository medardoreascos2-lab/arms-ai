import { MedarConversation } from "@/components/product/MedarConversation";
import { localMedarEnabled } from "@/lib/medarLocalConfig";

export default function ProductMedarPage() {
  return <main><MedarConversation localTestEnabled={localMedarEnabled(process.env)} /></main>;
}
