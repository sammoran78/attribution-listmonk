package core

import (
	"net/http"

	"github.com/jmoiron/sqlx/types"
	"github.com/labstack/echo/v4"
	"github.com/lib/pq"
)

// GetDashboardCharts returns chart data points to render on the dashboard.
func (c *Core) GetDashboardCharts(allLists bool, listIDs []int) (types.JSONText, error) {
	var out types.JSONText
	var err error
	if allLists {
		_ = c.refreshCache(matDashboardCharts, false)
		err = c.q.GetDashboardCharts.Get(&out)
	} else {
		// A shared materialized view contains other users' lists. Never use it
		// for restricted users, even when slow-query caching is enabled.
		err = c.q.GetScopedDashboardCharts.Get(&out, pq.Array(listIDs))
	}
	if err != nil {
		return nil, echo.NewHTTPError(http.StatusInternalServerError,
			c.i18n.Ts("globals.messages.errorFetching", "name", "dashboard charts", "error", pqErrMsg(err)))
	}

	return out, nil
}

// GetDashboardCounts returns stats counts to show on the dashboard.
func (c *Core) GetDashboardCounts(allLists bool, listIDs []int) (types.JSONText, error) {
	var out types.JSONText
	var err error
	if allLists {
		_ = c.refreshCache(matDashboardCounts, false)
		err = c.q.GetDashboardCounts.Get(&out)
	} else {
		err = c.q.GetScopedDashboardCounts.Get(&out, pq.Array(listIDs))
	}
	if err != nil {
		return nil, echo.NewHTTPError(http.StatusInternalServerError,
			c.i18n.Ts("globals.messages.errorFetching", "name", "dashboard stats", "error", pqErrMsg(err)))
	}

	return out, nil
}
