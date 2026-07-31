import { theme, type ThemeConfig } from "antd";
import { colors } from "./colors";

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 24,
  xxxl: 32,
} as const;

export const layoutTokens = {
  appPadding: 12,
  appGap: 12,
  sidebarWidth: 280,
  sidebarCompactWidth: 240,
  sidebarPadding: 20,
  workspaceMinWidth: 560,
  workspaceBarHeight: 56,
  panelPadding: 24,
  composerPadding: 16,
  conversationItemPaddingInline: 16,
  messageItemPaddingInline: 24,
  controlMinHeight: 44,
  radiusPanel: 10,
  breakpointTablet: 1200,
  breakpointMobile: 768,
  breakpointCompact: 480,
} as const;

export const antdTheme: ThemeConfig = {
  algorithm: theme.darkAlgorithm,
  token: {
    colorPrimary: colors.primary,
    colorPrimaryHover: colors.primaryHover,
    colorPrimaryActive: colors.primaryActive,
    colorBgBase: colors.bgBase,
    colorBgContainer: colors.bgContainer,
    colorBgElevated: colors.bgElevated,
    colorFillAlter: colors.fillAlter,
    colorTextBase: colors.textPrimary,
    colorTextSecondary: colors.textSecondary,
    colorTextDescription: colors.textDescription,
    colorTextDisabled: colors.textDisabled,
    colorBorder: colors.border,
    colorSuccess: colors.success,
    colorWarning: colors.warning,
    colorError: colors.danger,
    colorInfo: colors.info,
    sizeUnit: 4,
    sizeStep: 4,
    borderRadius: 8,
    borderRadiusLG: layoutTokens.radiusPanel,
    fontFamily: '"Open Sans", Inter, ui-sans-serif, system-ui, -apple-system, sans-serif',
  },
  components: {
    Button: {
      colorPrimary: colors.primary,
      colorPrimaryHover: colors.primaryHover,
      colorPrimaryActive: colors.primaryActive,
      borderRadius: 8,
      controlHeight: 40,
    },
    Input: {
      colorBgContainer: colors.input,
      activeBorderColor: colors.primaryHover,
      hoverBorderColor: colors.primary,
      colorTextPlaceholder: colors.textDescription,
    },
    Card: { colorBgContainer: colors.bgContainer },
    Modal: { contentBg: colors.bgContainer, headerBg: colors.bgContainer },
    List: { colorText: colors.textPrimary },
  },
};
