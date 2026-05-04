import { Button } from "@/components/ui/button";
import { useLanguage } from "@/i18n/LanguageContext";

export function LanguageToggle() {
  const { language, setLanguage } = useLanguage();

  const toggleLanguage = () => {
    setLanguage(language === "en" ? "ja" : "en");
  };

  return (
    <button
      type="button"
      onClick={toggleLanguage}
      className="flex items-center justify-center w-8 h-8 text-muted-foreground font-medium hover:bg-accent/50 hover:text-foreground transition-colors"
      aria-label={`Switch to ${language === "en" ? "Japanese" : "English"} mode`}
      title={`Toggle language`}
    >
      {language === "en" ? "EN" : "JP"}
    </button>
  );
}
