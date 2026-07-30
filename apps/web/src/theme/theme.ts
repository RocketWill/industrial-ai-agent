import { theme, type ThemeConfig } from "antd";
import { colors } from "./colors";

export const antdTheme: ThemeConfig = {
  algorithm: theme.darkAlgorithm,
  token: {
    colorPrimary: colors.primary,
    colorPrimaryHover: colors.accentHover,
    colorBgBase: colors.bgBase,
    colorBgContainer: colors.bgContainer,
    colorBgElevated: colors.bgElevated,
    colorFillAlter: colors.fillAlter,
    colorTextBase: colors.textPrimary,
    colorTextSecondary: colors.textSecondary,
    colorTextDescription: colors.textDescription,
    colorBorder: colors.border,
    borderRadius: 8,
    fontFamily: '"Open Sans", Inter, ui-sans-serif, system-ui, -apple-system, sans-serif',
  },
  components: {
    Button: {
      colorPrimary: colors.primary,
      colorPrimaryHover: colors.accentHover,
      colorPrimaryActive: colors.accent,
      borderRadius: 8,
      controlHeight: 40,
    },
    Input: {
      colorBgContainer: colors.fillAlter,
      activeBorderColor: colors.accentHover,
      hoverBorderColor: colors.primary,
      colorTextPlaceholder: colors.textDescription,
    },
    Card: { colorBgContainer: colors.bgContainer },
    Modal: { contentBg: colors.bgContainer, headerBg: colors.bgContainer },
    List: { colorText: colors.textPrimary },
  },
};
